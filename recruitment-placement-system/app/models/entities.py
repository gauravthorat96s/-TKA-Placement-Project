"""Domain entities that mirror the database tables. Build them with from_row() from a DB row."""
from dataclasses import dataclass, fields
from typing import Any, Dict, Optional


class _RowMixin:
    @classmethod
    def from_row(cls, row: Dict[str, Any]):
        """Create an entity from a dict row, ignoring columns the entity does not declare."""
        names = {f.name for f in fields(cls)}
        return cls(**{key: value for key, value in row.items() if key in names})


@dataclass
class User(_RowMixin):
    user_id: Optional[int] = None
    username: Optional[str] = None
    password_hash: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    role_id: Optional[int] = None
    status: Optional[str] = None
    last_login_at: Optional[Any] = None
    role_code: Optional[str] = None
    role_name: Optional[str] = None


@dataclass
class Candidate(_RowMixin):
    candidate_id: Optional[int] = None
    candidate_code: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    date_of_birth: Optional[Any] = None
    gender: Optional[str] = None
    qualification: Optional[str] = None
    college: Optional[str] = None
    university: Optional[str] = None
    passing_year: Optional[int] = None
    percentage: Optional[Any] = None
    cgpa: Optional[Any] = None
    backlog_count: int = 0
    primary_technology: Optional[str] = None
    current_location: Optional[str] = None
    preferred_location: Optional[str] = None
    profile_status: str = "ACTIVE"
    placement_status: str = "NOT_PLACED"


@dataclass
class Company(_RowMixin):
    company_id: Optional[int] = None
    company_code: Optional[str] = None
    company_name: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    location: Optional[str] = None
    company_type: Optional[str] = None
    hr_name: Optional[str] = None
    hr_email: Optional[str] = None
    hr_mobile: Optional[str] = None
    status: str = "ACTIVE"


@dataclass
class Job(_RowMixin):
    job_id: Optional[int] = None
    job_code: Optional[str] = None
    company_id: Optional[int] = None
    job_title: Optional[str] = None
    employment_type: str = "FULL_TIME"
    location: Optional[str] = None
    openings: Optional[int] = None
    min_package_lpa: Optional[Any] = None
    max_package_lpa: Optional[Any] = None
    min_percentage: Optional[Any] = None
    min_passing_year: Optional[int] = None
    max_passing_year: Optional[int] = None
    max_backlogs: int = 0
    experience_min_years: Optional[Any] = None
    qualification_rule: Optional[str] = None
    posted_date: Optional[Any] = None
    application_deadline: Optional[Any] = None
    status: str = "DRAFT"
    created_by: Optional[int] = None


@dataclass
class JobSkill(_RowMixin):
    job_id: Optional[int] = None
    skill_id: Optional[int] = None
    skill_name: Optional[str] = None
    minimum_level: Optional[str] = None
    mandatory_flag: int = 1


@dataclass
class CandidateSkill(_RowMixin):
    candidate_id: Optional[int] = None
    skill_id: Optional[int] = None
    skill_name: Optional[str] = None
    proficiency_level: Optional[str] = None
    years_experience: Optional[Any] = None
    is_primary: int = 0


@dataclass
class Application(_RowMixin):
    application_id: Optional[int] = None
    application_code: Optional[str] = None
    candidate_id: Optional[int] = None
    job_id: Optional[int] = None
    applied_at: Optional[Any] = None
    eligibility_status: str = "PENDING"
    eligibility_reason: Optional[str] = None
    application_status: str = "APPLIED"
    source: Optional[str] = None
    assigned_recruiter_id: Optional[int] = None


@dataclass
class InterviewRound(_RowMixin):
    interview_id: Optional[int] = None
    application_id: Optional[int] = None
    round_number: Optional[int] = None
    round_type: Optional[str] = None
    scheduled_date: Optional[Any] = None
    scheduled_time: Optional[Any] = None
    mode: Optional[str] = None
    interviewer_name: Optional[str] = None
    meeting_or_location: Optional[str] = None
    status: str = "SCHEDULED"


@dataclass
class InterviewFeedback(_RowMixin):
    feedback_id: Optional[int] = None
    interview_id: Optional[int] = None
    technical_rating: Optional[Any] = None
    communication_rating: Optional[Any] = None
    problem_solving_rating: Optional[Any] = None
    overall_rating: Optional[Any] = None
    recommendation: Optional[str] = None
    remarks: Optional[str] = None
    submitted_by: Optional[int] = None


@dataclass
class Offer(_RowMixin):
    offer_id: Optional[int] = None
    offer_code: Optional[str] = None
    application_id: Optional[int] = None
    designation: Optional[str] = None
    offered_package_lpa: Optional[Any] = None
    offer_date: Optional[Any] = None
    expected_joining_date: Optional[Any] = None
    offer_status: str = "OFFERED"
    remarks: Optional[str] = None


@dataclass
class Placement(_RowMixin):
    placement_id: Optional[int] = None
    candidate_id: Optional[int] = None
    company_id: Optional[int] = None
    job_id: Optional[int] = None
    offer_id: Optional[int] = None
    designation: Optional[str] = None
    final_package_lpa: Optional[Any] = None
    expected_joining_date: Optional[Any] = None
    actual_joining_date: Optional[Any] = None
    joining_status: str = "PENDING"
    placement_status: str = "ACTIVE"
