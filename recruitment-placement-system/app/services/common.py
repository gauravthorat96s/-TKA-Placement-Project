"""Helpers shared by the service layer: auditing, skill-link cleaning and state-transition wrapper."""
from app.db.repositories import ApplicationRepository, SkillRepository, UserRepository
from app.exceptions import NotFoundError, ValidationError
from app.models.enums import PROFICIENCY_LEVELS
from app.utils.logger import get_logger
from app.validation.validators import choice, parse_decimal, parse_int

_log = get_logger("rpms.audit")
_users = UserRepository()
_skills = SkillRepository()
_apps = ApplicationRepository()


def audit(cur, actor, module: str, action: str, record_id, description: str) -> None:
    """Write an activity_logs row (same transaction as the change) and a line to the application log."""
    _users.insert_activity(cur, actor.user_id, module, action, str(record_id), description[:500])
    _log.info("%s %s %s by user=%s: %s", module, action, record_id, actor.user_id, description)


def _check_skill_exists(cur, skill_id):
    if not _skills.get(cur, skill_id):
        raise NotFoundError(f"Skill {skill_id} does not exist.")


def clean_candidate_skills(cur, rows) -> list:
    """Input rows: {skill_id, proficiency_level, years_experience, is_primary}."""
    cleaned, seen = [], set()
    for row in rows or []:
        skill_id = parse_int(row.get("skill_id"), "Skill", required=True)
        if skill_id in seen:
            raise ValidationError("A skill can be listed only once per candidate.")
        seen.add(skill_id)
        _check_skill_exists(cur, skill_id)
        level = row.get("proficiency_level") or None
        if level is not None:
            level = choice(level, PROFICIENCY_LEVELS, "Proficiency level")
        years = parse_decimal(row.get("years_experience"), "Years of experience", minimum=0) or 0
        cleaned.append({"skill_id": skill_id, "proficiency_level": level, "years_experience": years,
                        "is_primary": bool(row.get("is_primary"))})
    return cleaned


def clean_job_skills(cur, rows) -> list:
    """Input rows: {skill_id, minimum_level, mandatory_flag}."""
    cleaned, seen = [], set()
    for row in rows or []:
        skill_id = parse_int(row.get("skill_id"), "Skill", required=True)
        if skill_id in seen:
            raise ValidationError("A skill can be listed only once per job.")
        seen.add(skill_id)
        _check_skill_exists(cur, skill_id)
        level = row.get("minimum_level") or None
        if level is not None:
            level = choice(level, PROFICIENCY_LEVELS, "Minimum level")
        cleaned.append({"skill_id": skill_id, "minimum_level": level,
                        "mandatory_flag": row.get("mandatory_flag", True) not in (False, 0, "0")})
    return cleaned


def get_application(cur, application_id):
    row = _apps.get(cur, application_id)
    if not row:
        raise NotFoundError("Application not found.")
    return row


def transition_application(cur, app: dict, new_status: str, actor, remarks=None) -> dict:
    """Validate the workflow rule, then update the application and append an audit-trail row."""
    from app.services.workflow import assert_application_transition
    old = app["application_status"]
    assert_application_transition(old, new_status)
    _apps.update_status(cur, app["application_id"], new_status)
    _apps.insert_history(cur, app["application_id"], old, new_status, remarks, actor.user_id)
    app["application_status"] = new_status
    return app
