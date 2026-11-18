"""Runtime configuration. Values come from environment variables with safe local defaults."""
import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_DIR = PROJECT_ROOT / "database"
REPORTS_SQL = DATABASE_DIR / "reports.sql"
LOG_FILE = Path(os.getenv("RPMS_LOG_FILE", PROJECT_ROOT / "logs" / "rpms.log"))
EXPORT_DIR = Path(os.getenv("RPMS_EXPORT_DIR", PROJECT_ROOT / "exports"))


@dataclass(frozen=True)
class DBConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


def load_db_config() -> DBConfig:
    return DBConfig(
        host=os.getenv("RPMS_DB_HOST", "localhost"),
        port=int(os.getenv("RPMS_DB_PORT", "3306")),
        user=os.getenv("RPMS_DB_USER", "rpms_app"),
        password=os.getenv("RPMS_DB_PASSWORD", ""),
        database=os.getenv("RPMS_DB_NAME", "rpms_db"),
    )
