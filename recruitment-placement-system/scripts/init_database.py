"""Create the database, tables and sample data from the SQL files in database/.

WARNING: database_schema.sql starts with DROP DATABASE rpms_db. Existing data in that database is erased.

    python scripts/init_database.py
"""
import sys
from pathlib import Path

import mysql.connector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import DATABASE_DIR, load_db_config  # noqa: E402


def split_statements(sql: str):
    """Split a SQL file into single statements. A statement ends at a line ending with ';'."""
    statements, buffer = [], []
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buffer.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(buffer))
            buffer = []
    return statements


def run_script(conn, path: Path) -> None:
    cursor = conn.cursor()
    for statement in split_statements(path.read_text(encoding="utf-8")):
        cursor.execute(statement)
        if cursor.with_rows:
            cursor.fetchall()  # read SELECT results so the cursor is free for the next statement
    conn.commit()
    cursor.close()
    print(f"Executed {path.name}")


def main() -> None:
    cfg = load_db_config()
    conn = mysql.connector.connect(host=cfg.host, port=cfg.port, user=cfg.user, password=cfg.password)
    try:
        run_script(conn, DATABASE_DIR / "database_schema.sql")
        run_script(conn, DATABASE_DIR / "sample_data.sql")
    finally:
        conn.close()
    print("Database ready. Demo logins use password Demo@123 (admin, amit.recruiter, sneha.recruiter, neha.placement, rahul.placement).")


if __name__ == "__main__":
    main()
