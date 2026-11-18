import unittest
from datetime import date
from decimal import Decimal

from app.models.entities import Candidate, CandidateSkill, Job, JobSkill
from app.services.eligibility_engine import EligibilityEngine, qualification_allowed

TODAY = date(2026, 10, 30)
JAVA, SQL, JDBC = 1, 3, 6


def make_job(**overrides):
    base = dict(job_id=1, job_code="JOB-2026-001", company_id=1, status="OPEN", min_percentage=Decimal("60"),
                min_passing_year=2024, max_passing_year=2026, max_backlogs=0, experience_min_years=Decimal("0"),
                qualification_rule="BE/BTech/MCA", application_deadline=date(2026, 11, 15))
    base.update(overrides)
    return Job.from_row(base)


def make_candidate(**overrides):
    base = dict(candidate_id=1, candidate_code="CAN-2026-0001", full_name="Rahul Patil", qualification="BE",
                passing_year=2025, percentage=Decimal("68.5"), backlog_count=0, profile_status="ACTIVE")
    base.update(overrides)
    return Candidate.from_row(base)


JOB_SKILLS = [
    JobSkill(job_id=1, skill_id=JAVA, skill_name="Java", minimum_level="INTERMEDIATE", mandatory_flag=1),
    JobSkill(job_id=1, skill_id=SQL, skill_name="SQL", minimum_level="INTERMEDIATE", mandatory_flag=1),
    JobSkill(job_id=1, skill_id=JDBC, skill_name="JDBC", minimum_level="BASIC", mandatory_flag=1),
]


def skills(*rows):
    return [CandidateSkill(candidate_id=1, skill_id=sid, skill_name=name, proficiency_level=lvl,
                           years_experience=Decimal(str(years))) for sid, name, lvl, years in rows]


GOOD_SKILLS = skills((JAVA, "Java", "INTERMEDIATE", 1), (SQL, "SQL", "INTERMEDIATE", 1), (JDBC, "JDBC", "BASIC", 0.5))


class QualificationTests(unittest.TestCase):
    def test_any_rule_accepts_everyone(self):
        self.assertTrue(qualification_allowed("BSc", "Any Graduate"))
        self.assertTrue(qualification_allowed(None, None))

    def test_prefix_match_for_long_qualification_names(self):
        self.assertTrue(qualification_allowed("BSc Computer Science", "BE/BTech/BCA/BSc/MCA"))

    def test_rejects_unlisted_qualification(self):
        self.assertFalse(qualification_allowed("MSc Computer Science", "BE/BTech/MCA"))
        self.assertFalse(qualification_allowed("BTech", "BE/MCA"))


class EngineTests(unittest.TestCase):
    engine = EligibilityEngine()

    def run_rules(self, candidate=None, job=None, job_skills=None, cand_skills=None):
        return self.engine.evaluate(candidate or make_candidate(), job or make_job(), job_skills or JOB_SKILLS,
                                    cand_skills if cand_skills is not None else GOOD_SKILLS, today=TODAY)

    def test_fully_qualified_candidate_is_eligible(self):
        result = self.run_rules()
        self.assertTrue(result.eligible)
        self.assertEqual(result.summary, "Meets eligibility criteria")

    def test_low_percentage_is_rejected(self):
        result = self.run_rules(candidate=make_candidate(percentage=Decimal("58")))
        self.assertFalse(result.eligible)
        self.assertTrue(any("below minimum" in r for r in result.reasons))

    def test_backlogs_over_limit_are_rejected(self):
        result = self.run_rules(candidate=make_candidate(backlog_count=2))
        self.assertIn("Backlogs 2 exceed allowed 0", result.reasons)

    def test_closed_job_is_rejected(self):
        result = self.run_rules(job=make_job(status="CLOSED"))
        self.assertIn("Job status is CLOSED, not OPEN", result.reasons)

    def test_expired_deadline_is_rejected(self):
        result = self.run_rules(job=make_job(application_deadline=date(2026, 10, 1)))
        self.assertIn("Application deadline has passed", result.reasons)

    def test_passing_year_window(self):
        result = self.run_rules(candidate=make_candidate(passing_year=2023))
        self.assertTrue(any("before 2024" in r for r in result.reasons))

    def test_missing_mandatory_skill(self):
        result = self.run_rules(cand_skills=GOOD_SKILLS[:2])
        self.assertIn("Missing required skill: JDBC", result.reasons)

    def test_skill_below_minimum_level(self):
        weak = skills((JAVA, "Java", "BASIC", 1), (SQL, "SQL", "INTERMEDIATE", 1), (JDBC, "JDBC", "BASIC", 1))
        result = self.run_rules(cand_skills=weak)
        self.assertIn("Java proficiency must be INTERMEDIATE", result.reasons)

    def test_optional_skill_is_not_required(self):
        optional = [JobSkill(job_id=1, skill_id=9, skill_name="Selenium", minimum_level="ADVANCED", mandatory_flag=0)]
        self.assertTrue(self.run_rules(job_skills=JOB_SKILLS + optional).eligible)

    def test_inactive_profile_is_rejected(self):
        result = self.run_rules(candidate=make_candidate(profile_status="ON_HOLD"))
        self.assertIn("Candidate profile is ON_HOLD", result.reasons)

    def test_multiple_reasons_are_all_reported(self):
        result = self.run_rules(candidate=make_candidate(passing_year=2023, backlog_count=3), cand_skills=[])
        self.assertGreaterEqual(len(result.reasons), 4)
        self.assertFalse(result.eligible)


if __name__ == "__main__":
    unittest.main()
