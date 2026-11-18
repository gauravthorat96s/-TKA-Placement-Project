"""Builds every service once, sharing one Database object. The CLI and tests use this."""
from app.db.connection import Database
from app.services.application_service import ApplicationService
from app.services.auth_service import AuthService
from app.services.candidate_service import CandidateService
from app.services.interview_service import InterviewService
from app.services.master_service import CompanyService, JobService
from app.services.placement_service import PlacementService
from app.services.report_service import ReportService


class Services:
    def __init__(self, db: Database):
        self.db = db
        self.auth = AuthService(db)
        self.candidates = CandidateService(db)
        self.companies = CompanyService(db)
        self.jobs = JobService(db)
        self.applications = ApplicationService(db)
        self.interviews = InterviewService(db)
        self.placements = PlacementService(db)
        self.reports = ReportService(db)
