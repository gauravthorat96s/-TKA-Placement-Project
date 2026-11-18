"""Recruitment workflow rules: which status changes are allowed. Pure data plus two checks."""
from app.exceptions import WorkflowError

APPLICATION_TRANSITIONS = {
    "APPLIED": {"ELIGIBILITY_VERIFIED", "REJECTED", "WITHDRAWN"},
    "ELIGIBILITY_VERIFIED": {"SHORTLISTED", "REJECTED", "WITHDRAWN"},
    "SHORTLISTED": {"INTERVIEW_SCHEDULED", "REJECTED", "WITHDRAWN"},
    "INTERVIEW_SCHEDULED": {"INTERVIEWED", "REJECTED", "WITHDRAWN"},
    "INTERVIEWED": {"INTERVIEW_SCHEDULED", "SELECTED", "REJECTED", "WITHDRAWN"},
    "SELECTED": {"OFFERED", "REJECTED", "WITHDRAWN"},
    "OFFERED": {"JOINED", "REJECTED", "WITHDRAWN"},
    "JOINED": set(),
    "REJECTED": set(),
    "WITHDRAWN": set(),
}

# Statuses a recruiter may set directly. The others are driven by interview, offer and joining events.
MANUAL_APPLICATION_STATUSES = {"ELIGIBILITY_VERIFIED", "SHORTLISTED", "REJECTED", "WITHDRAWN"}

OFFER_TRANSITIONS = {
    "OFFERED": {"ACCEPTED", "REJECTED", "EXPIRED", "WITHDRAWN"},
    "ACCEPTED": {"WITHDRAWN"},
    "REJECTED": set(),
    "EXPIRED": set(),
    "WITHDRAWN": set(),
}

# Interview recommendation -> application status it implies (after INTERVIEWED is reached).
FEEDBACK_TO_APPLICATION = {
    "NEXT_ROUND": "INTERVIEWED",
    "ON_HOLD": "INTERVIEWED",
    "SELECTED": "SELECTED",
    "REJECTED": "REJECTED",
}

# Application status implied by a change to the offer status (ACCEPTED leaves the application OFFERED).
OFFER_EFFECT_ON_APPLICATION = {"ACCEPTED": None, "REJECTED": "REJECTED", "EXPIRED": "REJECTED", "WITHDRAWN": "WITHDRAWN"}


def assert_application_transition(old: str, new: str) -> None:
    if new not in APPLICATION_TRANSITIONS.get(old, set()):
        raise WorkflowError(f"Application cannot move from {old} to {new}.")


def assert_offer_transition(old: str, new: str) -> None:
    if new not in OFFER_TRANSITIONS.get(old, set()):
        raise WorkflowError(f"Offer cannot move from {old} to {new}.")
