"""Flask web layer tests. They run the real routes and services on the SQLite stand-in database."""
import unittest

from app.services.container import Services
from app.web import create_app
from tests.sqlite_harness import SQLiteDatabase
from tests.test_services_end_to_end import FixedClockEngine

FAR_FUTURE = "2099-06-01"
NEW_CANDIDATE = {
    "full_name": "Web Candidate", "email": "web.candidate@example.com", "mobile": "9777777777",
    "date_of_birth": "", "gender": "", "qualification": "BE", "college": "", "university": "",
    "passing_year": "2025", "percentage": "72", "cgpa": "", "backlog_count": "0",
    "primary_technology": "Java", "current_location": "Pune", "preferred_location": "Pune",
    "profile_status": "ACTIVE", "skills": "1:INTERMEDIATE:1",
}


class WebTests(unittest.TestCase):
    def setUp(self):
        self.db = SQLiteDatabase()
        self.services = Services(self.db)
        self.services.applications.engine = FixedClockEngine()
        self.app = create_app(self.services)
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def login(self, username="amit.recruiter", password="Demo@123"):
        return self.client.post("/login", data={"username": username, "password": password}, follow_redirects=True)

    def text(self, response):
        return response.get_data(as_text=True)

    def test_login_failure_shows_message(self):
        self.assertIn("Invalid username or password.", self.text(self.login(password="wrong")))

    def test_pages_require_login(self):
        self.assertEqual(self.client.get("/candidates").status_code, 302)

    def test_all_pages_render_after_login(self):
        self.login()
        paths = ["/dashboard", "/candidates", "/candidates/new", "/candidates/3", "/candidates/3/edit",
                 "/companies", "/jobs", "/jobs/new", "/jobs/1/edit", "/applications", "/applications?history=41",
                 "/interviews", "/placements", "/reports", "/reports?name=recruitment_funnel"]
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_candidate_registration_through_form(self):
        self.login()
        response = self.client.post("/candidates/new", data=NEW_CANDIDATE, follow_redirects=True)
        self.assertIn("CAN-2026-0031", self.text(response))
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM candidate_skills WHERE candidate_id = 31"), 1)

    def test_validation_error_is_shown_and_form_kept(self):
        self.login()
        bad = dict(NEW_CANDIDATE, email="not-an-email", full_name="Keep Me")
        response = self.client.post("/candidates/new", data=bad)
        body = self.text(response)
        self.assertIn("Enter a valid email address.", body)
        self.assertIn("Keep Me", body)

    def test_apply_then_schedule_interview(self):
        self.login()
        response = self.client.post("/applications/apply",
                                    data={"candidate_id": "27", "job_id": "1", "source": "Portal"}, follow_redirects=True)
        self.assertIn("APP-2026-0051", self.text(response))
        response = self.client.post("/interviews/schedule", data={
            "application_id": "41", "round_type": "TECHNICAL", "interview_date": FAR_FUTURE,
            "interview_time": "10:00", "mode": "ONLINE"}, follow_redirects=True)
        self.assertIn("Interview scheduled", self.text(response))

    def test_eligibility_rejection_is_shown(self):
        self.login()
        response = self.client.post("/applications/apply",
                                    data={"candidate_id": "21", "job_id": "3", "source": "Portal"}, follow_redirects=True)
        self.assertIn("does not meet the eligibility criteria", self.text(response))
        self.assertIn("Missing required skill: Data Analytics", self.text(response))

    def test_role_rule_is_enforced_on_web(self):
        self.login("neha.placement")
        response = self.client.post("/applications/apply",
                                    data={"candidate_id": "27", "job_id": "1", "source": "Portal"}, follow_redirects=True)
        self.assertIn("cannot perform this action", self.text(response))

    def test_offer_creation_on_web(self):
        self.login("neha.placement")
        response = self.client.post("/placements/offers", data={
            "application_id": "48", "designation": "Analyst", "package_lpa": "3.2",
            "offer_date": FAR_FUTURE, "expected_joining_date": FAR_FUTURE}, follow_redirects=True)
        self.assertIn("Offer OFF-2099-", self.text(response))
        self.assertEqual(self.db.scalar("SELECT application_status FROM applications WHERE application_id = 48"), "OFFERED")

    def test_csv_export_is_utf8_with_bom(self):
        self.login()
        response = self.client.get("/reports/export?name=candidate_export")
        self.assertEqual(response.mimetype, "text/csv")
        self.assertTrue(response.get_data().startswith(b"\xef\xbb\xbf"))
        self.assertIn("candidate_code", self.text(response))

    def test_logout_clears_session(self):
        self.login()
        self.client.get("/logout")
        self.assertEqual(self.client.get("/dashboard").status_code, 302)


if __name__ == "__main__":
    unittest.main()
