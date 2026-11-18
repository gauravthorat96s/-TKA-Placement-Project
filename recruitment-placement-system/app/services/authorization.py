"""Role-based permissions. ADMIN holds every permission; other roles hold the subset listed here."""
from app.exceptions import AuthorizationError

ALL_PERMISSIONS = frozenset({
    "candidate:write", "company:write", "job:write", "application:write",
    "interview:write", "offer:write", "report:read",
})

ROLE_PERMISSIONS = {
    "ADMIN": ALL_PERMISSIONS,
    "RECRUITER": frozenset({"candidate:write", "job:write", "application:write", "interview:write", "report:read"}),
    "PLACEMENT_OFFICER": frozenset({"candidate:write", "company:write", "interview:write", "offer:write", "report:read"}),
}


def has_permission(user, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(getattr(user, "role_code", None), frozenset())


def require(user, permission: str) -> None:
    if not has_permission(user, permission):
        raise AuthorizationError(f"Your role ({getattr(user, 'role_code', 'unknown')}) cannot perform this action.")
