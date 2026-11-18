"""Candidate registration, maintenance, search, CSV bulk import and the 360-degree profile."""
from datetime import date

from app.db.connection import Database
from app.db.repositories import ApplicationRepository, CandidateRepository, OfferRepository
from app.exceptions import DuplicateRecordError, NotFoundError, RPMSError
from app.models.enums import CANDIDATE_PROFILE_STATUS
from app.services.authorization import require
from app.services.common import audit, clean_candidate_skills
from app.utils.file_io import read_csv
from app.validation.validators import (
    choice, optional_text, parse_date, parse_decimal, parse_int, require_text,
    validate_backlog_count, validate_email, validate_mobile, validate_percentage,
)


def _clean_candidate(form: dict) -> dict:
    return {
        "full_name": require_text(form.get("full_name"), "Please enter candidate name."),
        "email": validate_email(form.get("email")),
        "mobile": validate_mobile(form.get("mobile")),
        "date_of_birth": parse_date(form.get("date_of_birth"), "Date of birth"),
        "gender": optional_text(form.get("gender")),
        "qualification": require_text(form.get("qualification"), "Please select a qualification."),
        "college": optional_text(form.get("college")),
        "university": optional_text(form.get("university")),
        "passing_year": parse_int(form.get("passing_year"), "Passing year", required=True, minimum=1990, maximum=2035),
        "percentage": validate_percentage(form.get("percentage")),
        "cgpa": parse_decimal(form.get("cgpa"), "CGPA", minimum=0, maximum=10),
        "backlog_count": validate_backlog_count(form.get("backlog_count")),
        "primary_technology": optional_text(form.get("primary_technology")),
        "current_location": optional_text(form.get("current_location")),
        "preferred_location": optional_text(form.get("preferred_location")),
        "profile_status": choice(form.get("profile_status") or "ACTIVE", CANDIDATE_PROFILE_STATUS, "Profile status"),
    }


class CandidateService:
    def __init__(self, db: Database):
        self.db = db
        self.candidates = CandidateRepository()
        self.applications = ApplicationRepository()
        self.offers = OfferRepository()

    def register(self, actor, form: dict, skills=None) -> str:
        require(actor, "candidate:write")
        data = _clean_candidate(form)
        with self.db.transaction() as cur:
            if self.candidates.find_duplicate(cur, data["email"], data["mobile"]):
                raise DuplicateRecordError("A candidate with this email or mobile already exists.")
            clean_skills = clean_candidate_skills(cur, skills)
            data["candidate_code"] = f"CAN-{date.today().year}-{self.candidates.next_id(cur):04d}"
            data["placement_status"] = "NOT_PLACED"
            candidate_id = self.candidates.insert(cur, data)
            self.candidates.replace_skills(cur, candidate_id, clean_skills)
            audit(cur, actor, "CANDIDATE", "CREATE", data["candidate_code"], f"Registered {data['full_name']}")
        return data["candidate_code"]

    def update(self, actor, candidate_id: int, form: dict, skills=None) -> None:
        require(actor, "candidate:write")
        data = _clean_candidate(form)
        with self.db.transaction() as cur:
            current = self.candidates.get(cur, candidate_id)
            if not current:
                raise NotFoundError("Candidate not found.")
            if self.candidates.find_duplicate(cur, data["email"], data["mobile"], exclude_id=candidate_id):
                raise DuplicateRecordError("A candidate with this email or mobile already exists.")
            clean_skills = clean_candidate_skills(cur, skills) if skills is not None else None
            self.candidates.update(cur, candidate_id, data)
            if clean_skills is not None:
                self.candidates.replace_skills(cur, candidate_id, clean_skills)
            audit(cur, actor, "CANDIDATE", "UPDATE", current["candidate_code"], "Profile updated")

    def deactivate(self, actor, candidate_id: int) -> None:
        """Soft deactivation: history is kept, so the record is never hard deleted."""
        require(actor, "candidate:write")
        with self.db.transaction() as cur:
            current = self.candidates.get(cur, candidate_id)
            if not current:
                raise NotFoundError("Candidate not found.")
            self.candidates.update(cur, candidate_id, {"profile_status": "INACTIVE"})
            audit(cur, actor, "CANDIDATE", "DEACTIVATE", current["candidate_code"], "Profile set to INACTIVE")

    def import_csv(self, actor, path: str):
        """Register each CSV row in its own transaction. Bad rows are reported, good rows are kept."""
        require(actor, "candidate:write")
        imported, errors = 0, []
        for line_no, row in enumerate(read_csv(path), start=2):
            try:
                self.register(actor, row)
            except RPMSError as exc:
                errors.append(f"Line {line_no}: {exc}")
            else:
                imported += 1
        return imported, errors

    def search(self, filters: dict, limit: int = 50):
        with self.db.cursor() as cur:
            return self.candidates.search(cur, filters, limit)

    def profile(self, candidate_id: int) -> dict:
        """360-degree view: personal/academic data, skills, applications, offers and placements."""
        with self.db.cursor() as cur:
            candidate = self.candidates.get(cur, candidate_id)
            if not candidate:
                raise NotFoundError("Candidate not found.")
            return {
                "candidate": candidate,
                "skills": self.candidates.skills(cur, candidate_id),
                "applications": self.applications.search(cur, {"candidate_id": candidate_id}),
                "offers": self.offers.search_offers(cur, {"candidate_id": candidate_id}),
                "placements": self.offers.search_placements(cur, {"candidate_id": candidate_id}),
            }
