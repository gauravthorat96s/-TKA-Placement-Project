"""Interview rounds: scheduling, rescheduling, no-shows and feedback. Feedback drives the application status."""
from app.db.connection import Database
from app.db.repositories import ApplicationRepository, InterviewRepository
from app.exceptions import DuplicateRecordError, NotFoundError, WorkflowError
from app.models.enums import FEEDBACK_RECOMMENDATIONS, INTERVIEW_MODES, ROUND_TYPES
from app.services.authorization import require
from app.services.common import audit, get_application, transition_application
from app.services.workflow import FEEDBACK_TO_APPLICATION
from app.validation.validators import (
    choice, optional_text, parse_date, parse_time, validate_interview_date, validate_rating,
)

RATING_FIELDS = (
    ("technical_rating", "Technical rating"),
    ("communication_rating", "Communication rating"),
    ("problem_solving_rating", "Problem-solving rating"),
    ("overall_rating", "Overall rating"),
)


class InterviewService:
    def __init__(self, db: Database):
        self.db = db
        self.apps = ApplicationRepository()
        self.interviews = InterviewRepository()

    def schedule(self, actor, application_id: int, round_type: str, interview_date, interview_time=None,
                 mode: str = "ONLINE", interviewer: str = None, location: str = None) -> int:
        require(actor, "interview:write")
        round_type = choice(round_type, ROUND_TYPES, "Interview round")
        mode = choice(mode, INTERVIEW_MODES, "Mode")
        when = validate_interview_date(parse_date(interview_date, "Interview date", required=True))
        clock = parse_time(interview_time)
        with self.db.transaction() as cur:
            app = get_application(cur, application_id)
            round_number = self.interviews.max_round(cur, application_id) + 1
            interview_id = self.interviews.insert(cur, {
                "application_id": application_id,
                "round_number": round_number,
                "round_type": round_type,
                "scheduled_date": when,
                "scheduled_time": clock,
                "mode": mode,
                "interviewer_name": optional_text(interviewer),
                "meeting_or_location": optional_text(location),
                "status": "SCHEDULED",
            })
            transition_application(cur, app, "INTERVIEW_SCHEDULED", actor, f"Round {round_number} ({round_type}) scheduled")
            audit(cur, actor, "INTERVIEW", "SCHEDULE", interview_id,
                  f"Round {round_number} {round_type} for {app['application_code']} on {when}")
        return interview_id

    def reschedule(self, actor, interview_id: int, interview_date, interview_time=None) -> None:
        require(actor, "interview:write")
        when = validate_interview_date(parse_date(interview_date, "Interview date", required=True))
        clock = parse_time(interview_time)
        with self.db.transaction() as cur:
            iv = self._get(cur, interview_id)
            if iv["status"] not in ("SCHEDULED", "RESCHEDULED"):
                raise WorkflowError("Only scheduled interviews can be rescheduled.")
            self.interviews.update(cur, interview_id, {"scheduled_date": when, "scheduled_time": clock, "status": "RESCHEDULED"})
            audit(cur, actor, "INTERVIEW", "RESCHEDULE", interview_id, f"Moved to {when} {clock or ''}".strip())

    def mark_no_show(self, actor, interview_id: int) -> None:
        require(actor, "interview:write")
        with self.db.transaction() as cur:
            iv = self._get(cur, interview_id)
            if iv["status"] not in ("SCHEDULED", "RESCHEDULED"):
                raise WorkflowError("Only scheduled interviews can be marked as no-show.")
            self.interviews.update(cur, interview_id, {"status": "NO_SHOW"})
            audit(cur, actor, "INTERVIEW", "NO_SHOW", interview_id, "Candidate did not attend")

    def submit_feedback(self, actor, interview_id: int, recommendation: str, ratings: dict = None,
                        remarks: str = None) -> int:
        """Completes the interview, stores one feedback record, then updates the application."""
        require(actor, "interview:write")
        recommendation = choice(recommendation, FEEDBACK_RECOMMENDATIONS, "Recommendation")
        ratings = ratings or {}
        clean = {column: validate_rating(ratings.get(column), label) for column, label in RATING_FIELDS}
        with self.db.transaction() as cur:
            iv = self._get(cur, interview_id)
            if iv["status"] in ("SCHEDULED", "RESCHEDULED"):
                self.interviews.update(cur, interview_id, {"status": "COMPLETED"})
            elif iv["status"] != "COMPLETED":
                raise WorkflowError("Feedback can only be recorded for scheduled or completed interviews.")
            if self.interviews.feedback_for(cur, interview_id):
                raise DuplicateRecordError("Feedback is already recorded for this interview round.")
            feedback_id = self.interviews.insert_feedback(cur, {
                "interview_id": interview_id, **clean,
                "recommendation": recommendation,
                "remarks": optional_text(remarks),
                "submitted_by": actor.user_id,
            })
            app = get_application(cur, iv["application_id"])
            if app["application_status"] == "INTERVIEW_SCHEDULED":
                transition_application(cur, app, "INTERVIEWED", actor, "Interview completed")
            target = FEEDBACK_TO_APPLICATION[recommendation]
            if target != app["application_status"]:
                transition_application(cur, app, target, actor, f"Interview feedback: {recommendation}")
            audit(cur, actor, "INTERVIEW", "FEEDBACK", interview_id, f"Recommendation {recommendation}")
        return feedback_id

    def _get(self, cur, interview_id):
        iv = self.interviews.get(cur, interview_id)
        if not iv:
            raise NotFoundError("Interview not found.")
        return iv

    def search(self, filters: dict):
        with self.db.cursor() as cur:
            return self.interviews.search(cur, filters)
