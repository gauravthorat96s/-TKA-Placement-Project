"""Candidate applications: eligibility-gated apply, eligibility re-check and manual status changes."""
from datetime import date

from app.db.connection import Database
from app.db.repositories import ApplicationRepository, CandidateRepository, JobRepository
from app.exceptions import DuplicateRecordError, EligibilityError, NotFoundError, ValidationError, WorkflowError
from app.models.entities import Candidate, CandidateSkill, Job, JobSkill
from app.models.enums import APPLICATION_SOURCES, APPLICATION_STATUS
from app.services.authorization import require
from app.services.common import audit, get_application, transition_application
from app.services.eligibility_engine import EligibilityEngine
from app.services.workflow import MANUAL_APPLICATION_STATUSES
from app.validation.validators import choice


class ApplicationService:
    def __init__(self, db: Database):
        self.db = db
        self.candidates = CandidateRepository()
        self.jobs = JobRepository()
        self.apps = ApplicationRepository()
        self.engine = EligibilityEngine()

    def _evaluate(self, cur, cand_row: dict, job_row: dict):
        candidate = Candidate.from_row(cand_row)
        job = Job.from_row(job_row)
        job_skills = [JobSkill.from_row(r) for r in self.jobs.skills(cur, job.job_id)]
        cand_skills = [CandidateSkill.from_row(r) for r in self.candidates.skills(cur, candidate.candidate_id)]
        return self.engine.evaluate(candidate, job, job_skills, cand_skills)

    def apply(self, actor, candidate_id: int, job_id: int, source: str = "Portal") -> str:
        """Apply only after the eligibility engine passes. Duplicate applications are blocked."""
        require(actor, "application:write")
        source = choice(source, APPLICATION_SOURCES, "Source")
        with self.db.transaction() as cur:
            cand_row = self.candidates.get(cur, candidate_id)
            if not cand_row:
                raise NotFoundError("Candidate not found.")
            job_row = self.jobs.get(cur, job_id)
            if not job_row:
                raise NotFoundError("Job not found.")
            if self.apps.find_by_candidate_job(cur, candidate_id, job_id):
                raise DuplicateRecordError("Candidate has already applied for this job.")
            result = self._evaluate(cur, cand_row, job_row)
            if not result.eligible:
                raise EligibilityError("Candidate does not meet the eligibility criteria.", result.reasons)
            code = f"APP-{date.today().year}-{self.apps.next_id(cur):04d}"
            app_id = self.apps.insert(cur, {
                "application_code": code,
                "candidate_id": candidate_id,
                "job_id": job_id,
                "eligibility_status": "ELIGIBLE",
                "eligibility_reason": result.summary,
                "application_status": "APPLIED",
                "source": source,
                "assigned_recruiter_id": actor.user_id if actor.role_code == "RECRUITER" else None,
            })
            self.apps.insert_history(cur, app_id, None, "APPLIED", "Application submitted", actor.user_id)
            audit(cur, actor, "APPLICATION", "CREATE", code,
                  f"Candidate {cand_row['candidate_code']} applied to {job_row['job_code']}")
        return code

    def check_eligibility(self, actor, application_id: int):
        """Re-run the engine. Passing moves APPLIED -> ELIGIBILITY_VERIFIED; failing moves APPLIED -> REJECTED."""
        require(actor, "application:write")
        with self.db.transaction() as cur:
            app = get_application(cur, application_id)
            result = self._evaluate(cur, self.candidates.get(cur, app["candidate_id"]),
                                    self.jobs.get(cur, app["job_id"]))
            if result.eligible:
                self.apps.update_eligibility(cur, application_id, "ELIGIBLE", result.summary)
                if app["application_status"] == "APPLIED":
                    transition_application(cur, app, "ELIGIBILITY_VERIFIED", actor, "Eligibility verified")
            else:
                self.apps.update_eligibility(cur, application_id, "NOT_ELIGIBLE", result.summary)
                if app["application_status"] == "APPLIED":
                    transition_application(cur, app, "REJECTED", actor, f"Not eligible: {result.summary}")
            audit(cur, actor, "APPLICATION", "ELIGIBILITY", app["application_code"], result.summary)
        return result

    def change_status(self, actor, application_id: int, new_status: str, remarks: str = None) -> None:
        require(actor, "application:write")
        new_status = choice(new_status, APPLICATION_STATUS, "Application status")
        if new_status not in MANUAL_APPLICATION_STATUSES:
            raise WorkflowError(f"{new_status} is set by the interview or offer workflow, not manually.")
        with self.db.transaction() as cur:
            app = get_application(cur, application_id)
            old = app["application_status"]
            transition_application(cur, app, new_status, actor, remarks)
            audit(cur, actor, "APPLICATION", new_status, app["application_code"], f"{old} -> {new_status}")

    def history(self, application_id: int):
        with self.db.cursor() as cur:
            return self.apps.history(cur, application_id)

    def search(self, filters: dict):
        with self.db.cursor() as cur:
            return self.apps.search(cur, filters)
