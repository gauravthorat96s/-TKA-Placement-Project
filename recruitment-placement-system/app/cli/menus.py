"""Console application flow: login, role-aware main menu, and guided prompts for every workflow.
Business rules live in the services; this module only collects input and shows results."""
import getpass
from datetime import date

from app.config import EXPORT_DIR, load_db_config
from app.db.connection import Database
from app.exceptions import RPMSError
from app.services.authorization import has_permission
from app.services.container import Services
from app.utils.logger import setup_logging

CANDIDATE_FIELDS = [
    ("full_name", "Full name", True), ("email", "Email", True), ("mobile", "Mobile (10 digits)", True),
    ("date_of_birth", "Date of birth (YYYY-MM-DD)", False), ("gender", "Gender", False),
    ("qualification", "Qualification (e.g. BE, BTech, MCA, BCA, BSc Computer Science)", True),
    ("college", "College", False), ("university", "University", False), ("passing_year", "Passing year", True),
    ("percentage", "Percentage (0-100)", False), ("cgpa", "CGPA", False), ("backlog_count", "Backlog count", False),
    ("primary_technology", "Primary technology", False), ("current_location", "Current location", False),
    ("preferred_location", "Preferred location", False), ("profile_status", "Profile status (ACTIVE/INACTIVE/ON_HOLD/BLACKLISTED)", False),
]
COMPANY_FIELDS = [
    ("company_name", "Company name", True), ("industry", "Industry", True), ("website", "Website", False),
    ("location", "Primary location", True), ("company_type", "Company type (MNC/STARTUP/MID_SIZE/CONSULTANCY)", True),
    ("hr_name", "HR contact name", True), ("hr_email", "HR email", True), ("hr_mobile", "HR mobile", False),
]
JOB_FIELDS = [
    ("company_id", "Company ID", True), ("job_title", "Job title", True),
    ("employment_type", "Employment type (FULL_TIME/INTERNSHIP/CONTRACT)", True), ("location", "Location", True),
    ("openings", "Number of openings", True), ("min_package_lpa", "Minimum package (LPA)", False),
    ("max_package_lpa", "Maximum package (LPA)", False), ("min_percentage", "Minimum percentage", False),
    ("min_passing_year", "Minimum passing year", False), ("max_passing_year", "Maximum passing year", False),
    ("max_backlogs", "Maximum backlogs allowed", True), ("experience_min_years", "Minimum experience (years)", False),
    ("posted_date", "Posted date (YYYY-MM-DD)", True), ("application_deadline", "Application deadline (YYYY-MM-DD)", True),
    ("status", "Status (DRAFT/OPEN/CLOSED/CANCELLED)", True),
]


# ----------------------------------------------------------------- prompt helpers
def ask(label, default=None, required=False):
    shown = f" [{default}]" if default not in (None, "") else ""
    while True:
        value = input(f"  {label}{shown}: ").strip()
        if value == "" and default not in (None, ""):
            return str(default)
        if value or not required:
            return value
        print("  -> This field is required.")


def ask_int(label, required=True):
    while True:
        text = ask(label, required=required)
        if text == "" and not required:
            return None
        try:
            return int(text)
        except ValueError:
            print("  -> Enter a whole number.")


def ask_form(fields, current=None):
    current = current or {}
    form = {}
    for key, label, required in fields:
        value = current.get(key)
        form[key] = ask(label, default="" if value is None else value, required=required)
    return form


def ask_skills(prompt_text, level_key):
    """Format: skill_id:LEVEL:years (comma separated). level_key is 'proficiency_level' or 'minimum_level'."""
    raw = ask(prompt_text)
    rows = []
    for item in [part.strip() for part in raw.split(",") if part.strip()]:
        parts = item.split(":")
        row = {"skill_id": parts[0]}
        if len(parts) > 1:
            row[level_key] = parts[1]
        if len(parts) > 2:
            row["years_experience"] = parts[2]
        rows.append(row)
    return rows


def show(rows, columns=None):
    rows = list(rows)
    if not rows:
        print("  (no records)")
        return
    columns = columns or list(rows[0].keys())
    widths = {c: min(max(len(str(c)), *(len(str(r.get(c, ""))) for r in rows)), 30) for c in columns}
    print("  " + "  ".join(str(c).ljust(widths[c])[:widths[c]] for c in columns))
    print("  " + "  ".join("-" * widths[c] for c in columns))
    for row in rows:
        print("  " + "  ".join(str(row.get(c, "")).ljust(widths[c])[:widths[c]] for c in columns))


def menu(title, options):
    """options: list of (label, handler). Returns after the user picks 0 (back)."""
    while True:
        print(f"\n== {title} ==")
        for number, (label, _) in enumerate(options, 1):
            print(f"  {number}. {label}")
        print("  0. Back")
        choice = input("Choose: ").strip()
        if choice in ("0", ""):
            return
        if not choice.isdigit() or not 1 <= int(choice) <= len(options):
            print("  Invalid choice.")
            continue
        try:
            options[int(choice) - 1][1]()
        except RPMSError as exc:
            print(f"\n  ! {exc}")
            for reason in getattr(exc, "reasons", []):
                print(f"     - {reason}")


# ----------------------------------------------------------------- application
class Console:
    def __init__(self, services: Services, user):
        self.s = services
        self.user = user

    def run(self):
        sections = [
            ("Candidates", self.candidates_menu),
            ("Companies", self.companies_menu),
            ("Jobs", self.jobs_menu),
            ("Applications", self.applications_menu),
            ("Interviews", self.interviews_menu),
            ("Offers & placements", self.placements_menu),
            ("Reports", self.reports_menu),
        ]
        while True:
            print(f"\nSigned in as {self.user.full_name} ({self.user.role_code})")
            options = [(label, handler) for label, handler in sections]
            print("\n== Main menu ==")
            for number, (label, _) in enumerate(options, 1):
                print(f"  {number}. {label}")
            print("  0. Log out")
            choice = input("Choose: ").strip()
            if choice in ("0", ""):
                print("Logged out.")
                return
            if choice.isdigit() and 1 <= int(choice) <= len(options):
                try:
                    options[int(choice) - 1][1]()
                except RPMSError as exc:
                    print(f"\n  ! {exc}")
                    for reason in getattr(exc, "reasons", []):
                        print(f"     - {reason}")
            else:
                print("  Invalid choice.")

    # ------------------------------------------------------------- candidates
    def candidates_menu(self):
        menu("Candidates", [
            ("Search candidates", self.search_candidates),
            ("Register candidate", self.register_candidate),
            ("View 360-degree profile", self.view_profile),
            ("Update candidate", self.update_candidate),
            ("Deactivate candidate", self.deactivate_candidate),
            ("Import candidates from CSV", self.import_candidates),
        ])

    def search_candidates(self):
        filters = {"full_name": ask("Name contains"), "primary_technology": ask("Technology (Java/Python/Testing/Data Analytics)"),
                   "passing_year": ask("Passing year"), "placement_status": ask("Placement status (NOT_PLACED/PLACED)")}
        show(self.s.candidates.search(filters), ["candidate_id", "candidate_code", "full_name", "mobile",
                                                  "qualification", "passing_year", "primary_technology", "profile_status", "placement_status"])

    def _candidate_skills_prompt(self):
        return ask_skills("Skills as skill_id:LEVEL:years, comma separated (e.g. 1:INTERMEDIATE:1.5, 3:BASIC:0.5)", "proficiency_level")

    def register_candidate(self):
        form = ask_form(CANDIDATE_FIELDS)
        code = self.s.candidates.register(self.user, form, skills=self._candidate_skills_prompt())
        print(f"  Candidate registered: {code}")

    def view_profile(self):
        profile = self.s.candidates.profile(ask_int("Candidate ID"))
        c = profile["candidate"]
        print(f"\n  {c['candidate_code']}  {c['full_name']}  [{c['profile_status']} / {c['placement_status']}]")
        print(f"  {c['qualification']}, {c['passing_year']}, {c['percentage']}%, backlogs {c['backlog_count']}, {c['primary_technology']}")
        print("\n  Skills:"); show(profile["skills"], ["skill_name", "proficiency_level", "years_experience"])
        print("\n  Applications:"); show(profile["applications"], ["application_code", "job_code", "application_status", "eligibility_status"])
        print("\n  Offers:"); show(profile["offers"], ["offer_code", "designation", "offered_package_lpa", "offer_status"])
        print("\n  Placements:"); show(profile["placements"], ["placement_id", "company_name", "designation", "joining_status"])

    def update_candidate(self):
        candidate_id = ask_int("Candidate ID")
        current = self.s.candidates.profile(candidate_id)["candidate"]
        form = ask_form(CANDIDATE_FIELDS, current=current)
        self.s.candidates.update(self.user, candidate_id, form)
        print("  Candidate updated.")

    def deactivate_candidate(self):
        self.s.candidates.deactivate(self.user, ask_int("Candidate ID"))
        print("  Candidate set to INACTIVE (history retained).")

    def import_candidates(self):
        imported, errors = self.s.candidates.import_csv(self.user, ask("CSV file path", required=True))
        print(f"  Imported {imported} candidate(s).")
        for line in errors:
            print(f"  ! {line}")

    # ------------------------------------------------------------- companies
    def companies_menu(self):
        menu("Companies", [
            ("List companies", lambda: show(self.s.companies.search({}), ["company_id", "company_code", "company_name", "industry", "location", "company_type", "status", "open_jobs"])),
            ("Add company", self.add_company),
            ("Deactivate company", lambda: (self.s.companies.deactivate(self.user, ask_int("Company ID")), print("  Company set to INACTIVE."))),
        ])

    def add_company(self):
        code = self.s.companies.create(self.user, ask_form(COMPANY_FIELDS))
        print(f"  Company added: {code}")

    # ------------------------------------------------------------- jobs
    def jobs_menu(self):
        menu("Job openings", [
            ("List jobs", lambda: show(self.s.jobs.search({"status": ask("Status filter (blank = all)")}),
                                       ["job_id", "job_code", "company_name", "job_title", "location", "openings", "application_deadline", "status", "applications"])),
            ("Create job", self.create_job),
            ("Change job status", self.change_job_status),
        ])

    def create_job(self):
        form = ask_form(JOB_FIELDS, current={"posted_date": date.today().isoformat(), "status": "DRAFT", "max_backlogs": "0"})
        form["qualifications"] = [q.strip() for q in ask("Allowed qualifications (comma separated, blank = any)").split(",") if q.strip()]
        skills = ask_skills("Required skills as skill_id:MINIMUM_LEVEL, comma separated (e.g. 1:INTERMEDIATE, 3:BASIC)", "minimum_level")
        code = self.s.jobs.create(self.user, form, skills=skills)
        print(f"  Job created: {code}")

    def change_job_status(self):
        self.s.jobs.set_status(self.user, ask_int("Job ID"), ask("New status (DRAFT/OPEN/CLOSED/CANCELLED)", required=True))
        print("  Job status updated.")

    # ------------------------------------------------------------- applications
    def applications_menu(self):
        menu("Applications", [
            ("Apply candidate to job", self.apply_candidate),
            ("Check eligibility", self.check_eligibility),
            ("Change status (shortlist / reject / withdraw)", self.change_application_status),
            ("List applications", self.list_applications),
            ("View status history", lambda: show(self.s.applications.history(ask_int("Application ID")))),
        ])

    def apply_candidate(self):
        code = self.s.applications.apply(self.user, ask_int("Candidate ID"), ask_int("Job ID"),
                                         ask("Source (Portal/Recruiter/Referral/Internal)", default="Portal"))
        print(f"  Application submitted: {code}")

    def check_eligibility(self):
        result = self.s.applications.check_eligibility(self.user, ask_int("Application ID"))
        print(f"  {'ELIGIBLE' if result.eligible else 'NOT ELIGIBLE'}: {result.summary}")

    def change_application_status(self):
        self.s.applications.change_status(self.user, ask_int("Application ID"),
                                          ask("New status (ELIGIBILITY_VERIFIED/SHORTLISTED/REJECTED/WITHDRAWN)", required=True),
                                          ask("Remarks"))
        print("  Status updated.")

    def list_applications(self):
        show(self.s.applications.search({"application_status": ask("Status filter (blank = all)")}),
             ["application_id", "application_code", "candidate", "job_code", "company_name", "eligibility_status", "application_status"])

    # ------------------------------------------------------------- interviews
    def interviews_menu(self):
        menu("Interviews", [
            ("Schedule interview round", self.schedule_interview),
            ("Reschedule interview", self.reschedule_interview),
            ("Mark no-show", lambda: (self.s.interviews.mark_no_show(self.user, ask_int("Interview ID")), print("  Marked as no-show."))),
            ("Record feedback (completes the round)", self.record_feedback),
            ("Pending interviews", lambda: show(self.s.interviews.search({"pending_only": True}),
                                                ["interview_id", "candidate", "company_name", "round_type", "scheduled_date", "scheduled_time", "mode", "status"])),
        ])

    def schedule_interview(self):
        iv = self.s.interviews.schedule(
            self.user, ask_int("Application ID"), ask("Round type (APTITUDE/TECHNICAL/MANAGERIAL/HR)", required=True),
            ask("Interview date (YYYY-MM-DD)", required=True), ask("Time (HH:MM)"),
            ask("Mode (ONLINE/OFFLINE/TELEPHONIC)", default="ONLINE"), ask("Interviewer name"), ask("Meeting link or venue"))
        print(f"  Interview scheduled (ID {iv}).")

    def reschedule_interview(self):
        self.s.interviews.reschedule(self.user, ask_int("Interview ID"), ask("New date (YYYY-MM-DD)", required=True), ask("New time (HH:MM)"))
        print("  Interview rescheduled.")

    def record_feedback(self):
        iv_id = ask_int("Interview ID")
        ratings = {col: ask(f"{label} (0-5, blank = none)") for col, label in (
            ("technical_rating", "Technical"), ("communication_rating", "Communication"),
            ("problem_solving_rating", "Problem solving"), ("overall_rating", "Overall"))}
        recommendation = ask("Recommendation (NEXT_ROUND/SELECTED/REJECTED/ON_HOLD)", required=True)
        self.s.interviews.submit_feedback(self.user, iv_id, recommendation, ratings, ask("Remarks"))
        print("  Feedback recorded.")

    # ------------------------------------------------------------- offers & placements
    def placements_menu(self):
        menu("Offers & placements", [
            ("Create offer for a SELECTED application", self.create_offer),
            ("Update offer status", self.update_offer),
            ("Confirm joining (creates placement)", self.confirm_joining),
            ("List offers", lambda: show(self.s.placements.list_offers({"offer_status": ask("Status filter (blank = all)")}),
                                         ["offer_id", "offer_code", "candidate", "job_code", "designation", "offered_package_lpa", "offer_status"])),
            ("List placements", lambda: show(self.s.placements.list_placements({"joining_status": ask("Joining status filter (blank = all)")}),
                                             ["placement_id", "candidate_code", "candidate", "company_name", "designation", "final_package_lpa", "joining_status"])),
        ])

    def create_offer(self):
        code = self.s.placements.create_offer(
            self.user, ask_int("Application ID"), ask("Designation", required=True), ask("Offered package (LPA)", required=True),
            ask("Offer date (YYYY-MM-DD)", required=True), ask("Expected joining date (YYYY-MM-DD)"), ask("Remarks"))
        print(f"  Offer issued: {code}")

    def update_offer(self):
        self.s.placements.update_offer_status(self.user, ask_int("Offer ID"),
                                              ask("New status (ACCEPTED/REJECTED/EXPIRED/WITHDRAWN)", required=True), ask("Remarks"))
        print("  Offer status updated.")

    def confirm_joining(self):
        pid = self.s.placements.confirm_joining(self.user, ask_int("Offer ID"),
                                                ask("Joining status (JOINED/NOT_JOINED/DEFERRED/NO_SHOW)", required=True),
                                                ask("Actual joining date (YYYY-MM-DD), required when JOINED"))
        print(f"  Joining recorded (placement ID {pid}).")

    # ------------------------------------------------------------- reports
    def reports_menu(self):
        menu("Reports", [
            ("Dashboard summary", self.show_dashboard),
            ("Run a report", self.run_report),
            ("Export a report to CSV", self.export_report),
        ])

    def show_dashboard(self):
        for key, value in self.s.reports.dashboard().items():
            print(f"  {key.replace('_', ' ').capitalize():22s} {value}")

    def _pick_report(self):
        names = self.s.reports.available()
        for number, (name, title) in enumerate(names, 1):
            print(f"  {number}. {title}  ({name})")
        index = ask_int("Report number")
        return names[index - 1][0]

    def run_report(self):
        name = self._pick_report()
        filters = {"date_from": ask("From date (YYYY-MM-DD, blank = none)"), "date_to": ask("To date (YYYY-MM-DD, blank = none)")}
        show(self.s.reports.run(name, filters))

    def export_report(self):
        name = self._pick_report()
        path = EXPORT_DIR / f"{name}_{date.today().isoformat()}.csv"
        rows = self.s.reports.export_csv(name, path)
        print(f"  Exported {rows} row(s) to {path}")


# ----------------------------------------------------------------- entry point
def login(services: Services):
    print("\nRecruitment & Placement Management System")
    for _ in range(3):
        username = input("  Username (blank to exit): ").strip()
        if not username:
            return None
        password = getpass.getpass("  Password: ")
        try:
            return services.auth.login(username, password)
        except RPMSError as exc:
            print(f"  ! {exc}")
    print("  Too many failed attempts.")
    return None


def run():
    setup_logging()
    services = Services(Database(load_db_config()))
    try:
        user = login(services)
        if user is not None:
            Console(services, user).run()
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye.")
