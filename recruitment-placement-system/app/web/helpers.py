"""Presentation helpers: status badges, skill-text parsing, CSV output."""
import csv
import io

from markupsafe import Markup, escape

BADGE_CLASS = {
    "b-green": {"ACTIVE", "OPEN", "JOINED", "PLACED", "ELIGIBLE", "ACCEPTED", "COMPLETED"},
    "b-blue": {"APPLIED", "ELIGIBILITY_VERIFIED", "SHORTLISTED", "INTERVIEW_SCHEDULED", "SCHEDULED", "RESCHEDULED", "OFFERED"},
    "b-purple": {"SELECTED"},
    "b-amber": {"INTERVIEWED", "ON_HOLD", "DRAFT", "PENDING", "DEFERRED", "NEXT_ROUND"},
    "b-red": {"REJECTED", "NOT_ELIGIBLE", "CLOSED", "INACTIVE", "NO_SHOW", "EXPIRED", "WITHDRAWN", "CANCELLED",
              "BLACKLISTED", "NOT_JOINED", "LOCKED"},
}
_CLASS_OF = {status: cls for cls, names in BADGE_CLASS.items() for status in names}


def badge(value):
    text = "" if value is None else str(value)
    cls = _CLASS_OF.get(text, "b-grey")
    return Markup(f'<span class="badge {cls}">{escape(text)}</span>')


def parse_skills(text: str, level_key: str):
    """'1:INTERMEDIATE:1.5, 3:BASIC' -> list of skill dicts."""
    rows = []
    for item in (text or "").split(","):
        parts = [p.strip() for p in item.split(":")]
        if not parts[0]:
            continue
        row = {"skill_id": parts[0]}
        if len(parts) > 1 and parts[1]:
            row[level_key] = parts[1].upper()
        if len(parts) > 2 and parts[2]:
            row["years_experience"] = parts[2]
        rows.append(row)
    return rows


def skills_to_text(skill_rows, level_key: str, years: bool) -> str:
    out = []
    for s in skill_rows:
        part = f"{s['skill_id']}:{s.get(level_key) or ''}"
        if years:
            part += f":{s.get('years_experience') or 0}"
        out.append(part)
    return ", ".join(out)


def rows_to_csv(rows) -> str:
    buffer = io.StringIO()
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return "\ufeff" + buffer.getvalue()  # BOM so Excel shows Devanagari/Marathi text correctly


def register_filters(app):
    app.jinja_env.filters["badge"] = badge
