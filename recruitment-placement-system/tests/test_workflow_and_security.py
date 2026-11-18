import unittest
from types import SimpleNamespace

from app.exceptions import AuthorizationError, WorkflowError
from app.services import workflow as wf
from app.services.authorization import require
from app.utils.security import hash_password, verify_password
from app.utils.file_io import read_csv, write_csv
from app.services.report_service import load_named_queries
from app.config import REPORTS_SQL, DATABASE_DIR
import tempfile, os


class WorkflowTests(unittest.TestCase):
    def test_happy_path_is_allowed(self):
        path = ["APPLIED", "ELIGIBILITY_VERIFIED", "SHORTLISTED", "INTERVIEW_SCHEDULED", "INTERVIEWED",
                "SELECTED", "OFFERED", "JOINED"]
        for old, new in zip(path, path[1:]):
            wf.assert_application_transition(old, new)

    def test_cannot_skip_stages(self):
        with self.assertRaises(WorkflowError):
            wf.assert_application_transition("APPLIED", "SELECTED")
        with self.assertRaises(WorkflowError):
            wf.assert_application_transition("SHORTLISTED", "OFFERED")

    def test_terminal_statuses_cannot_change(self):
        for terminal in ("JOINED", "REJECTED", "WITHDRAWN"):
            with self.assertRaises(WorkflowError):
                wf.assert_application_transition(terminal, "APPLIED")

    def test_offer_cannot_be_reopened(self):
        wf.assert_offer_transition("OFFERED", "ACCEPTED")
        with self.assertRaises(WorkflowError):
            wf.assert_offer_transition("REJECTED", "ACCEPTED")
        with self.assertRaises(WorkflowError):
            wf.assert_offer_transition("ACCEPTED", "REJECTED")

    def test_feedback_targets_are_valid_application_states(self):
        for recommendation, target in wf.FEEDBACK_TO_APPLICATION.items():
            self.assertIn(target, wf.APPLICATION_TRANSITIONS, recommendation)

    def test_manual_statuses_exclude_system_driven_states(self):
        for system_driven in ("OFFERED", "JOINED", "INTERVIEW_SCHEDULED", "INTERVIEWED", "SELECTED"):
            self.assertNotIn(system_driven, wf.MANUAL_APPLICATION_STATUSES)


class SecurityTests(unittest.TestCase):
    def test_hash_round_trip(self):
        stored = hash_password("S3cret!")
        self.assertTrue(verify_password("S3cret!", stored))
        self.assertFalse(verify_password("wrong", stored))
        self.assertNotIn("S3cret!", stored)

    def test_malformed_hash_is_rejected(self):
        self.assertFalse(verify_password("x", "plain-text"))
        self.assertFalse(verify_password("x", None))

    def test_seeded_demo_hashes_match_demo_password(self):
        sample = (DATABASE_DIR / "sample_data.sql").read_text(encoding="utf-8")
        import re
        hashes = re.findall(r"'(pbkdf2_sha256\$[^']+)'", sample)
        self.assertEqual(len(hashes), 5)
        self.assertTrue(all(verify_password("Demo@123", h) for h in hashes))


class AuthorizationTests(unittest.TestCase):
    def user(self, role):
        return SimpleNamespace(role_code=role, user_id=1)

    def test_admin_has_all_permissions(self):
        require(self.user("ADMIN"), "offer:write")

    def test_recruiter_cannot_create_offers(self):
        with self.assertRaises(AuthorizationError):
            require(self.user("RECRUITER"), "offer:write")

    def test_placement_officer_cannot_schedule_jobs(self):
        with self.assertRaises(AuthorizationError):
            require(self.user("PLACEMENT_OFFICER"), "job:write")


class FileAndReportTests(unittest.TestCase):
    def test_named_queries_are_loaded(self):
        queries = load_named_queries(REPORTS_SQL)
        for name in ("dashboard_summary", "recruitment_funnel", "company_wise_placements", "pending_interviews"):
            self.assertIn(name, queries)
            self.assertTrue(queries[name]["sql"].rstrip().endswith(";"))
        self.assertEqual(queries["recruitment_funnel"]["title"], "Recruitment funnel (cumulative stages)")

    def test_csv_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.csv")
            self.assertEqual(write_csv(path, [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]), 2)
            rows = read_csv(path)
            self.assertEqual(rows, [{"a": "1", "b": "x"}, {"a": "2", "b": "y"}])


if __name__ == "__main__":
    unittest.main()
