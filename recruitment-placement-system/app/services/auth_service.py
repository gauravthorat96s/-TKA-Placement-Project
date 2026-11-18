"""Login and session identity."""
from app.db.connection import Database
from app.db.repositories import UserRepository
from app.exceptions import AuthenticationError, ValidationError
from app.models.entities import User
from app.utils.security import verify_password

_users = UserRepository()


class AuthService:
    def __init__(self, db: Database):
        self.db = db

    def login(self, username: str, password: str) -> User:
        username = (username or "").strip()
        if not username or not password:
            raise ValidationError("Username and password are required.")
        with self.db.transaction() as cur:
            row = _users.get_by_username(cur, username)
            if not row or not verify_password(password, row["password_hash"]):
                raise AuthenticationError("Invalid username or password.")
            if row["status"] != "ACTIVE":
                raise AuthenticationError(f"This account is {row['status']}. Contact the administrator.")
            _users.touch_login(cur, row["user_id"])
        return User.from_row(row)
