"""Candidate Eligibility Engine: pure business rules with no database access, so it is easy to test.

A candidate may apply only if every rule passes. Each failed rule is returned as a reason.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from app.models.entities import Candidate, CandidateSkill, Job, JobSkill

PROFICIENCY_RANK = {"BASIC": 1, "INTERMEDIATE": 2, "ADVANCED": 3}


@dataclass
class EligibilityResult:
    eligible: bool
    reasons: List[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return "Meets eligibility criteria" if self.eligible else "; ".join(self.reasons)


def qualification_allowed(candidate_qualification: Optional[str], rule: Optional[str]) -> bool:
    """rule is a readable list such as 'BE/BTech/MCA'. Empty or 'Any ...' means no restriction.
    A candidate value such as 'BSc Computer Science' matches the token 'BSc' (prefix match)."""
    if not rule or not rule.strip() or rule.strip().lower().startswith("any"):
        return True
    if not candidate_qualification:
        return False
    value = candidate_qualification.strip().lower()
    return any(value.startswith(token.strip().lower()) for token in rule.split("/") if token.strip())


class EligibilityEngine:
    def evaluate(self, candidate: Candidate, job: Job, job_skills: List[JobSkill],
                 candidate_skills: List[CandidateSkill], today: Optional[date] = None) -> EligibilityResult:
        today = today or date.today()
        reasons: List[str] = []

        if job.status != "OPEN":
            reasons.append(f"Job status is {job.status}, not OPEN")
        if job.application_deadline and job.application_deadline < today:
            reasons.append("Application deadline has passed")
        if candidate.profile_status != "ACTIVE":
            reasons.append(f"Candidate profile is {candidate.profile_status}")
        if not qualification_allowed(candidate.qualification, job.qualification_rule):
            reasons.append(f"Qualification {candidate.qualification} is not allowed for this job")

        if job.min_percentage is not None:
            if candidate.percentage is None:
                reasons.append("Percentage is missing")
            elif candidate.percentage < job.min_percentage:
                reasons.append(f"Percentage {candidate.percentage} is below minimum {job.min_percentage}")

        if job.min_passing_year and candidate.passing_year < job.min_passing_year:
            reasons.append(f"Passing year {candidate.passing_year} is before {job.min_passing_year}")
        if job.max_passing_year and candidate.passing_year > job.max_passing_year:
            reasons.append(f"Passing year {candidate.passing_year} is after {job.max_passing_year}")

        if candidate.backlog_count > job.max_backlogs:
            reasons.append(f"Backlogs {candidate.backlog_count} exceed allowed {job.max_backlogs}")

        best_experience = max((cs.years_experience or 0 for cs in candidate_skills), default=0)
        if job.experience_min_years and best_experience < job.experience_min_years:
            reasons.append(f"Experience {best_experience} years is below required {job.experience_min_years}")

        by_skill = {cs.skill_id: cs for cs in candidate_skills}
        for required in job_skills:
            if not required.mandatory_flag:
                continue
            held = by_skill.get(required.skill_id)
            if held is None:
                reasons.append(f"Missing required skill: {required.skill_name}")
            elif required.minimum_level and (
                PROFICIENCY_RANK.get(held.proficiency_level or "", 0) < PROFICIENCY_RANK[required.minimum_level]
            ):
                reasons.append(f"{required.skill_name} proficiency must be {required.minimum_level}")

        return EligibilityResult(eligible=not reasons, reasons=reasons)
