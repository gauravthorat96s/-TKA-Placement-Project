"""Company (employer) master and job requirement management, including the eligibility criteria."""
from datetime import date

from app.db.connection import Database
from app.db.repositories import CompanyRepository, JobRepository
from app.exceptions import NotFoundError, ValidationError, WorkflowError
from app.models.enums import COMPANY_STATUS, COMPANY_TYPES, EMPLOYMENT_TYPES, JOB_STATUS
from app.services.authorization import require
from app.services.common import audit, clean_job_skills
from app.validation.validators import (
    choice, optional_text, parse_date, parse_decimal, parse_int, require_text,
    validate_backlog_count, validate_deadline, validate_email, validate_mobile,
    validate_openings, validate_package_range, validate_percentage, validate_year_window,
)


class CompanyService:
    def __init__(self, db: Database):
        self.db = db
        self.companies = CompanyRepository()

    @staticmethod
    def _clean(form: dict) -> dict:
        hr_mobile = optional_text(form.get("hr_mobile"))
        return {
            "company_name": require_text(form.get("company_name"), "Company name is required."),
            "industry": require_text(form.get("industry"), "Industry is required."),
            "website": optional_text(form.get("website")),
            "location": require_text(form.get("location"), "Primary location is required."),
            "company_type": choice(form.get("company_type"), COMPANY_TYPES, "Company type"),
            "hr_name": require_text(form.get("hr_name"), "HR contact name is required."),
            "hr_email": validate_email(form.get("hr_email")),
            "hr_mobile": validate_mobile(hr_mobile) if hr_mobile else None,
            "status": choice(form.get("status") or "ACTIVE", COMPANY_STATUS, "Status"),
        }

    def create(self, actor, form: dict) -> str:
        require(actor, "company:write")
        data = self._clean(form)
        with self.db.transaction() as cur:
            data["company_code"] = f"COM-{self.companies.next_id(cur):03d}"
            self.companies.insert(cur, data)
            audit(cur, actor, "COMPANY", "CREATE", data["company_code"], f"Added {data['company_name']}")
        return data["company_code"]

    def update(self, actor, company_id: int, form: dict) -> None:
        require(actor, "company:write")
        data = self._clean(form)
        with self.db.transaction() as cur:
            current = self.companies.get(cur, company_id)
            if not current:
                raise NotFoundError("Company not found.")
            self.companies.update(cur, company_id, data)
            audit(cur, actor, "COMPANY", "UPDATE", current["company_code"], "Company details updated")

    def deactivate(self, actor, company_id: int) -> None:
        """Companies are set INACTIVE, never deleted, so job history stays intact."""
        require(actor, "company:write")
        with self.db.transaction() as cur:
            current = self.companies.get(cur, company_id)
            if not current:
                raise NotFoundError("Company not found.")
            self.companies.update(cur, company_id, {"status": "INACTIVE"})
            audit(cur, actor, "COMPANY", "DEACTIVATE", current["company_code"], "Company set to INACTIVE")

    def search(self, filters: dict):
        with self.db.cursor() as cur:
            return self.companies.search(cur, filters)

    def detail(self, company_id: int):
        with self.db.cursor() as cur:
            company = self.companies.get(cur, company_id)
            if not company:
                raise NotFoundError("Company not found.")
            return company


def _qualification_rule(value):
    if isinstance(value, (list, tuple)):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return "/".join(parts) or None
    return optional_text(value)


class JobService:
    def __init__(self, db: Database):
        self.db = db
        self.jobs = JobRepository()
        self.companies = CompanyRepository()

    def _clean(self, cur, form: dict) -> dict:
        company_id = parse_int(form.get("company_id"), "Company", required=True)
        company = self.companies.get(cur, company_id)
        if not company or company["status"] != "ACTIVE":
            raise ValidationError("Select an active company for this job.")
        posted = parse_date(form.get("posted_date"), "Posted date", required=True)
        deadline = parse_date(form.get("application_deadline"), "Application deadline", required=True)
        validate_deadline(posted, deadline)
        min_pkg = parse_decimal(form.get("min_package_lpa"), "Minimum package", minimum=0)
        max_pkg = parse_decimal(form.get("max_package_lpa"), "Maximum package", minimum=0)
        validate_package_range(min_pkg, max_pkg)
        min_year = parse_int(form.get("min_passing_year"), "Minimum passing year", minimum=1990, maximum=2035)
        max_year = parse_int(form.get("max_passing_year"), "Maximum passing year", minimum=1990, maximum=2035)
        validate_year_window(min_year, max_year)
        return {
            "company_id": company_id,
            "job_title": require_text(form.get("job_title"), "Position title is required."),
            "employment_type": choice(form.get("employment_type") or "FULL_TIME", EMPLOYMENT_TYPES, "Employment type"),
            "location": require_text(form.get("location"), "Job location is required."),
            "openings": validate_openings(form.get("openings")),
            "min_package_lpa": min_pkg,
            "max_package_lpa": max_pkg,
            "min_percentage": validate_percentage(form.get("min_percentage")),
            "min_passing_year": min_year,
            "max_passing_year": max_year,
            "max_backlogs": validate_backlog_count(form.get("max_backlogs")),
            "experience_min_years": parse_decimal(form.get("experience_min_years"), "Experience", minimum=0) or 0,
            "qualification_rule": _qualification_rule(form.get("qualifications")),
            "posted_date": posted,
            "application_deadline": deadline,
            "status": choice(form.get("status") or "DRAFT", JOB_STATUS, "Job status"),
        }

    def create(self, actor, form: dict, skills=None) -> str:
        require(actor, "job:write")
        with self.db.transaction() as cur:
            data = self._clean(cur, form)
            clean_skills = clean_job_skills(cur, skills)
            data["job_code"] = f"JOB-{date.today().year}-{self.jobs.next_id(cur):03d}"
            data["created_by"] = actor.user_id
            job_id = self.jobs.insert(cur, data)
            self.jobs.replace_skills(cur, job_id, clean_skills)
            audit(cur, actor, "JOB", "CREATE", data["job_code"], f"Created {data['job_title']}")
        return data["job_code"]

    def update(self, actor, job_id: int, form: dict, skills=None) -> None:
        require(actor, "job:write")
        with self.db.transaction() as cur:
            current = self.jobs.get(cur, job_id)
            if not current:
                raise NotFoundError("Job not found.")
            data = self._clean(cur, form)
            self.jobs.update(cur, job_id, data)
            if skills is not None:
                self.jobs.replace_skills(cur, job_id, clean_job_skills(cur, skills))
            audit(cur, actor, "JOB", "UPDATE", current["job_code"], "Job requirements updated")

    def set_status(self, actor, job_id: int, status: str) -> None:
        require(actor, "job:write")
        status = choice(status, JOB_STATUS, "Job status")
        with self.db.transaction() as cur:
            current = self.jobs.get(cur, job_id)
            if not current:
                raise NotFoundError("Job not found.")
            if status == "DRAFT" and self.jobs.application_count(cur, job_id) > 0:
                raise WorkflowError("A job with applications cannot return to DRAFT. Close or cancel it instead.")
            self.jobs.update(cur, job_id, {"status": status})
            audit(cur, actor, "JOB", "STATUS", current["job_code"], f"Status {current['status']} -> {status}")

    def search(self, filters: dict):
        with self.db.cursor() as cur:
            return self.jobs.search(cur, filters)

    def detail(self, job_id: int) -> dict:
        with self.db.cursor() as cur:
            job = self.jobs.get(cur, job_id)
            if not job:
                raise NotFoundError("Job not found.")
            return {"job": job, "skills": self.jobs.skills(cur, job_id)}
