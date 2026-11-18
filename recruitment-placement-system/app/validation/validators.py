"""Input validation and parsing. Messages follow the prototype validation list (UI spec, section 8)."""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable, Optional

from app.exceptions import ValidationError

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def require_text(value, message: str) -> str:
    text = _text(value)
    if not text:
        raise ValidationError(message)
    return text


def optional_text(value) -> Optional[str]:
    return _text(value) or None


def choice(value, options: Iterable[str], field: str) -> str:
    """Case-insensitive match against the allowed list; returns the canonical option spelling."""
    options = tuple(options)
    text = _text(value).upper()
    for option in options:
        if option.upper() == text:
            return option
    raise ValidationError(f"{field} must be one of: {', '.join(options)}.")


def validate_email(value, required: bool = True) -> Optional[str]:
    text = _text(value)
    if not text:
        if required:
            raise ValidationError("Enter a valid email address.")
        return None
    if not _EMAIL_RE.match(text):
        raise ValidationError("Enter a valid email address.")
    return text.lower()


def validate_mobile(value) -> str:
    digits = re.sub(r"[\s-]", "", _text(value))
    if not re.fullmatch(r"\d{10}", digits):
        raise ValidationError("Mobile number must contain 10 digits.")
    return digits


def _check_range(number, field, minimum, maximum):
    below = minimum is not None and number < minimum
    above = maximum is not None and number > maximum
    if below or above:
        if minimum is not None and maximum is not None:
            detail = f"between {minimum} and {maximum}"
        elif minimum is not None:
            detail = f"at least {minimum}"
        else:
            detail = f"at most {maximum}"
        raise ValidationError(f"{field} must be {detail}.")
    return number


def parse_int(value, field: str, required: bool = False, minimum=None, maximum=None) -> Optional[int]:
    text = _text(value)
    if not text:
        if required:
            raise ValidationError(f"{field} is required.")
        return None
    try:
        number = int(text)
    except ValueError as exc:
        raise ValidationError(f"{field} must be a whole number.") from exc
    return _check_range(number, field, minimum, maximum)


def parse_decimal(value, field: str, required: bool = False, minimum=None, maximum=None) -> Optional[Decimal]:
    text = _text(value)
    if not text:
        if required:
            raise ValidationError(f"{field} is required.")
        return None
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValidationError(f"{field} must be a number.") from exc
    _check_range(number, field, minimum, maximum)
    return number


def parse_date(value, field: str, required: bool = False) -> Optional[date]:
    if isinstance(value, date):
        return value
    text = _text(value)
    if not text:
        if required:
            raise ValidationError(f"{field} is required.")
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValidationError(f"{field} must be a valid date in YYYY-MM-DD format.") from exc


def parse_time(value) -> Optional[str]:
    text = _text(value)
    if not text:
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).strftime("%H:%M:%S")
        except ValueError:
            continue
    raise ValidationError("Interview time must use HH:MM (24-hour) format.")


def validate_percentage(value) -> Optional[Decimal]:
    number = parse_decimal(value, "Percentage")
    if number is not None and not (Decimal(0) <= number <= Decimal(100)):
        raise ValidationError("Percentage must be between 0 and 100.")
    return number


def validate_backlog_count(value) -> int:
    number = parse_int(value, "Backlog count")
    if number is None:
        return 0
    if number < 0:
        raise ValidationError("Backlog count cannot be negative.")
    return number


def validate_openings(value) -> int:
    number = parse_int(value, "Number of openings", required=True)
    if number <= 0:
        raise ValidationError("Number of openings must be greater than zero.")
    return number


def validate_deadline(posted: date, deadline: date) -> None:
    if deadline < posted:
        raise ValidationError("Application deadline cannot be before posted date.")


def validate_package_range(minimum, maximum) -> None:
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValidationError("Minimum package cannot exceed maximum package.")


def validate_year_window(minimum, maximum) -> None:
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValidationError("Minimum passing year cannot exceed maximum passing year.")


def validate_interview_date(value: date, today: Optional[date] = None) -> date:
    if value < (today or date.today()):
        raise ValidationError("Interview date cannot be in the past.")
    return value


def validate_rating(value, field: str) -> Optional[Decimal]:
    return parse_decimal(value, field, minimum=0, maximum=5)
