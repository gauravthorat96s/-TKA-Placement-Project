"""Application exception hierarchy. Every RPMSError message is safe to show to the user."""


class RPMSError(Exception):
    """Base class for expected application errors."""


class ValidationError(RPMSError):
    """Input failed a format or business rule."""


class NotFoundError(RPMSError):
    """The requested record does not exist."""


class DuplicateRecordError(RPMSError):
    """A uniqueness rule or duplicate-application rule was violated."""


class EligibilityError(RPMSError):
    """The candidate does not satisfy the job's eligibility criteria."""

    def __init__(self, message, reasons=None):
        super().__init__(message)
        self.reasons = list(reasons or [])


class WorkflowError(RPMSError):
    """A status transition is not allowed by the recruitment workflow."""


class AuthenticationError(RPMSError):
    """Login failed."""


class AuthorizationError(RPMSError):
    """The user's role does not permit the action."""


class DatabaseError(RPMSError):
    """Connection or transaction failure. The transaction has been rolled back."""
