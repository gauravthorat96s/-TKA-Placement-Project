"""Runs the real services against the seeded database (SQLite stand-in). Covers the full
candidate -> application -> interview -> offer -> joining workflow, business-rule rejections,
transaction rollback, and CSV import. Eligibility uses a fixed 'today' so results do not depend on the clock."""
import os
import tempfile
import unittest
from datetime import date

from app.exceptions import (DatabaseError, DuplicateRecordError, EligibilityError, NotFoundError,
                            RPMSError, ValidationError, WorkflowError, AuthenticationError, AuthorizationError)
from app.services.container import Services
from app.services.eligibility_engine import EligibilityEngine
from tests.sqlite_harness import SQLiteDatabase

FAR_FUTURE = "2099-06-01"
FIXED_TODAY = date(2026, 10, 30)


class FixedClockEngine(EligibilityEngine):
    def evaluate(self, candidate, job, job_skills, candidate_skills, today=None):
        return super().evaluate(candidate, job, job_skills, candidate_skills, today=FIXED_TODAY)


CANDIDATE_FORM = {
    "full_name": "Test Candidate", "email": "test.candidate@example.com", "mobile": "9111111111",
    "qualification": "BE", "passing_year": "2025", "percentage": "70", "backlog_count": "0",
    "primary_technology": "Java", "current_location": "Pune", "preferred_location": "Pune",
}


class WorkflowEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.db = SQLiteDatabase()
        self.s = Services(self.db)
        self.s.applications.engine = FixedClockEngine()
        self.recruiter = self.s.auth.login("amit.recruiter", "Demo@123")
        self.officer = self.s.auth.login("neha.placement", "Demo@123")
        self.admin = self.s.auth.login("admin", "Demo@123")

    def app_status(self, application_id):
        return self.db.scalar("SELECT application_status FROM applications WHERE application_id = ?", (application_id,))

    # ------------------------------------------------------------------ authentication
    def test_login_roles_and_failures(self):
        self.assertEqual(self.recruiter.role_code, "RECRUITER")
        with self.assertRaises(AuthenticationError):
            self.s.auth.login("amit.recruiter", "wrong-password")
        with self.assertRaises(AuthenticationError):
            self.s.auth.login("nobody", "Demo@123")
        self.db.conn.execute("UPDATE users SET status = 'LOCKED' WHERE username = 'sneha.recruiter'")
        with self.assertRaises(AuthenticationError):
            self.s.auth.login("sneha.recruiter", "Demo@123")

    def test_role_permissions_are_enforced_in_services(self):
        with self.assertRaises(AuthorizationError):
            self.s.placements.create_offer(self.recruiter, 48, "X", "4", "2026-11-01")
        with self.assertRaises(AuthorizationError):
            self.s.companies.create(self.recruiter, {})

    # ------------------------------------------------------------------ candidates
    def test_register_candidate_and_reject_duplicates(self):
        code = self.s.candidates.register(self.recruiter, CANDIDATE_FORM, skills=[{"skill_id": 1, "proficiency_level": "INTERMEDIATE", "years_experience": "1"}])
        self.assertEqual(code, "CAN-2026-0031")
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM candidate_skills WHERE candidate_id = 31"), 1)
        with self.assertRaises(DuplicateRecordError):
            self.s.candidates.register(self.recruiter, CANDIDATE_FORM)

    def test_candidate_validation_messages(self):
        bad = dict(CANDIDATE_FORM, email="bad-email", full_name="")
        with self.assertRaises(ValidationError) as ctx:
            self.s.candidates.register(self.recruiter, bad)
        self.assertEqual(str(ctx.exception), "Please enter candidate name.")
        with self.assertRaises(ValidationError) as ctx:
            self.s.candidates.register(self.recruiter, dict(CANDIDATE_FORM, percentage="101", email="x@example.com", mobile="9222222222"))
        self.assertEqual(str(ctx.exception), "Percentage must be between 0 and 100.")

    def test_csv_import_keeps_good_rows_and_reports_bad_ones(self):
        content = ("full_name,email,mobile,qualification,passing_year,percentage,backlog_count,primary_technology\n"
                   "Good One,good.one@example.com,9333333333,BE,2025,72,0,Java\n"
                   "Dup Mail,good.one@example.com,9444444444,BE,2025,72,0,Java\n"
                   "Bad Pct,bad.pct@example.com,9555555555,BE,2025,150,0,Java\n")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "candidates.csv")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            imported, errors = self.s.candidates.import_csv(self.recruiter, path)
        self.assertEqual(imported, 1)
        self.assertEqual(len(errors), 2)
        self.assertIn("Line 3", errors[0])

    def test_profile_is_360_view(self):
        profile = self.s.candidates.profile(3)
        self.assertEqual(profile["candidate"]["candidate_code"], "CAN-2026-0003")
        self.assertTrue(profile["applications"])
        self.assertTrue(profile["offers"])
        self.assertTrue(profile["placements"])

    def test_deactivate_is_soft(self):
        self.s.candidates.deactivate(self.recruiter, 20)
        self.assertEqual(self.db.scalar("SELECT profile_status FROM candidates WHERE candidate_id = 20"), "INACTIVE")
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM candidates WHERE candidate_id = 20"), 1)

    # ------------------------------------------------------------------ applications & eligibility
    def test_apply_requires_eligibility_and_blocks_duplicates(self):
        with self.assertRaises(EligibilityError) as ctx:
            self.s.applications.apply(self.recruiter, 21, 3)  # candidate lacks Data Analytics skill
        self.assertEqual(str(ctx.exception), "Candidate does not meet the eligibility criteria.")
        self.assertTrue(any("Data Analytics" in r for r in ctx.exception.reasons))

        code = self.s.applications.apply(self.recruiter, 27, 1)
        self.assertTrue(code.startswith("APP-2026-"))
        with self.assertRaises(DuplicateRecordError) as ctx:
            self.s.applications.apply(self.recruiter, 27, 1)
        self.assertEqual(str(ctx.exception), "Candidate has already applied for this job.")

    def test_check_eligibility_moves_application_forward(self):
        result = self.s.applications.check_eligibility(self.recruiter, 41)
        self.assertTrue(result.eligible)
        self.assertEqual(self.app_status(41), "SHORTLISTED")  # already past APPLIED: status unchanged

    def test_recruiter_cannot_set_system_driven_status(self):
        with self.assertRaises(WorkflowError):
            self.s.applications.change_status(self.recruiter, 41, "OFFERED")
        with self.assertRaises(WorkflowError):
            self.s.applications.change_status(self.recruiter, 50, "SHORTLISTED")  # APPLIED cannot skip to SHORTLISTED

    def test_manual_rejection_writes_history(self):
        self.s.applications.change_status(self.recruiter, 50, "WITHDRAWN", "Candidate withdrew")
        self.assertEqual(self.app_status(50), "WITHDRAWN")
        history = self.s.applications.history(50)
        self.assertEqual(history[-1]["new_status"], "WITHDRAWN")

    # ------------------------------------------------------------------ interviews -> offer -> joining
    def test_full_recruitment_cycle(self):
        # Application 41 is SHORTLISTED. Round 1 -> NEXT_ROUND; round 2 -> SELECTED.
        iv1 = self.s.interviews.schedule(self.recruiter, 41, "TECHNICAL", FAR_FUTURE, "10:00", "ONLINE", "Interviewer A")
        self.assertEqual(self.app_status(41), "INTERVIEW_SCHEDULED")
        self.s.interviews.submit_feedback(self.recruiter, iv1, "NEXT_ROUND", {"technical_rating": "4", "overall_rating": "4"}, "Good")
        self.assertEqual(self.app_status(41), "INTERVIEWED")
        with self.assertRaises(DuplicateRecordError):
            self.s.interviews.submit_feedback(self.recruiter, iv1, "SELECTED")

        iv2 = self.s.interviews.schedule(self.recruiter, 41, "HR", FAR_FUTURE, "15:00", "TELEPHONIC")
        self.assertEqual(self.db.scalar("SELECT round_number FROM interview_rounds WHERE interview_id = ?", (iv2,)), 2)
        self.s.interviews.submit_feedback(self.recruiter, iv2, "SELECTED")
        self.assertEqual(self.app_status(41), "SELECTED")

        offer_code = self.s.placements.create_offer(self.officer, 41, "Associate Java Developer", "4.5", FAR_FUTURE, "2099-07-01")
        self.assertTrue(offer_code.startswith("OFF-"))
        self.assertEqual(self.app_status(41), "OFFERED")
        offer_id = self.db.scalar("SELECT offer_id FROM offers WHERE offer_code = ?", (offer_code,))

        self.s.placements.update_offer_status(self.officer, offer_id, "ACCEPTED")
        placement_id = self.s.placements.confirm_joining(self.officer, offer_id, "JOINED", "2099-07-01")
        self.assertTrue(placement_id)
        self.assertEqual(self.app_status(41), "JOINED")
        self.assertEqual(self.db.scalar("SELECT placement_status FROM candidates WHERE candidate_id = 21"), "PLACED")

        with self.assertRaises(DuplicateRecordError):
            self.s.placements.confirm_joining(self.officer, offer_id, "JOINED", "2099-07-01")

    def test_offer_requires_selected_status_and_is_single(self):
        with self.assertRaises(WorkflowError):
            self.s.placements.create_offer(self.officer, 41, "Role", "4", FAR_FUTURE)  # still SHORTLISTED
        code = self.s.placements.create_offer(self.officer, 48, "Data Analytics Trainee", "3.2", FAR_FUTURE)
        self.assertEqual(self.app_status(48), "OFFERED")
        self.assertTrue(code)
        with self.assertRaises(WorkflowError):  # application is no longer SELECTED, so a second offer is refused
            self.s.placements.create_offer(self.officer, 48, "Role", "4", FAR_FUTURE)

    def test_joining_failure_rolls_back_everything(self):
        # Offer 5 (application 4) is ACCEPTED and has no placement yet.
        before = self.db.scalar("SELECT COUNT(*) FROM placements")
        with self.assertRaises(DatabaseError):
            self.s.placements.confirm_joining(self.officer, 5, "JOINED", "2026-10-29", simulate_failure=True)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM placements"), before)
        self.assertEqual(self.db.scalar("SELECT placement_status FROM candidates WHERE candidate_id = 2"), "NOT_PLACED")
        self.assertEqual(self.app_status(4), "OFFERED")

    def test_joining_requires_accepted_offer_and_joining_date(self):
        with self.assertRaises(WorkflowError):
            self.s.placements.confirm_joining(self.officer, 4, "JOINED", "2026-10-29")  # offer 4 is only OFFERED
        with self.assertRaises(ValidationError):
            self.s.placements.confirm_joining(self.officer, 5, "JOINED", None)

    def test_offer_status_transitions(self):
        with self.assertRaises(WorkflowError):
            self.s.placements.update_offer_status(self.officer, 1, "OFFERED")  # cannot reopen an accepted offer
        self.s.placements.update_offer_status(self.officer, 4, "REJECTED", "Candidate declined")
        self.assertEqual(self.app_status(29), "REJECTED")

    def test_interview_date_in_past_is_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            self.s.interviews.schedule(self.recruiter, 41, "HR", "2020-01-01")
        self.assertEqual(str(ctx.exception), "Interview date cannot be in the past.")

    def test_no_show_and_reschedule(self):
        iv = self.db.scalar("SELECT interview_id FROM interview_rounds WHERE status = 'SCHEDULED' ORDER BY interview_id LIMIT 1")
        self.s.interviews.reschedule(self.recruiter, iv, FAR_FUTURE, "09:30")
        self.assertEqual(self.db.scalar("SELECT status FROM interview_rounds WHERE interview_id = ?", (iv,)), "RESCHEDULED")
        self.s.interviews.mark_no_show(self.recruiter, iv)
        with self.assertRaises(WorkflowError):
            self.s.interviews.reschedule(self.recruiter, iv, FAR_FUTURE)

    # ------------------------------------------------------------------ master data & reports
    def test_job_rules(self):
        base = {"company_id": "1", "job_title": "Trainee", "openings": "5", "employment_type": "FULL_TIME",
                "location": "Pune", "min_percentage": "60", "min_passing_year": "2024", "max_passing_year": "2026",
                "max_backlogs": "0", "qualifications": ["BE", "BTech"], "posted_date": "2026-11-01",
                "application_deadline": "2026-12-01", "status": "OPEN"}
        with self.assertRaises(ValidationError) as ctx:
            self.s.jobs.create(self.admin, dict(base, openings="0"))
        self.assertEqual(str(ctx.exception), "Number of openings must be greater than zero.")
        with self.assertRaises(ValidationError) as ctx:
            self.s.jobs.create(self.admin, dict(base, application_deadline="2026-10-01"))
        self.assertEqual(str(ctx.exception), "Application deadline cannot be before posted date.")
        with self.assertRaises(ValidationError):
            self.s.jobs.create(self.admin, dict(base, min_package_lpa="6", max_package_lpa="5"))
        code = self.s.jobs.create(self.admin, base, skills=[{"skill_id": 1, "minimum_level": "BASIC"}])
        self.assertEqual(code, "JOB-2026-013")
        self.assertEqual(self.db.scalar("SELECT qualification_rule FROM jobs WHERE job_code = ?", (code,)), "BE/BTech")

    def test_job_with_applications_cannot_return_to_draft(self):
        with self.assertRaises(WorkflowError):
            self.s.jobs.set_status(self.admin, 1, "DRAFT")
        self.s.jobs.set_status(self.admin, 1, "CLOSED")
        self.assertEqual(self.db.scalar("SELECT status FROM jobs WHERE job_id = 1"), "CLOSED")

    def test_company_deactivation_keeps_record(self):
        self.s.companies.deactivate(self.admin, 8)
        self.assertEqual(self.db.scalar("SELECT status FROM companies WHERE company_id = 8"), "INACTIVE")

    def test_reports_run_and_export(self):
        dash = self.s.reports.dashboard()
        self.assertEqual(dash["total_candidates"], 30)
        self.assertEqual(dash["placed"], 3)
        self.assertEqual(len(self.s.reports.run("candidates_by_technology")), 4)
        self.assertEqual(self.s.reports.run("placement_register", {"company_id": 1})[0]["company_name"], "TechNova Solutions")
        with tempfile.TemporaryDirectory() as tmp:
            rows = self.s.reports.export_csv("candidate_export", os.path.join(tmp, "c.csv"))
        self.assertEqual(rows, 30)
        with self.assertRaises(NotFoundError):
            self.s.reports.run("no_such_report")

    def test_audit_trail_is_written(self):
        before = self.db.scalar("SELECT COUNT(*) FROM activity_logs")
        self.s.candidates.deactivate(self.recruiter, 19)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM activity_logs"), before + 1)


if __name__ == "__main__":
    unittest.main()
