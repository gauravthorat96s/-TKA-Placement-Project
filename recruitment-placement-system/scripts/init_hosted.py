"""Create tables and demo data in an EXISTING database (for PythonAnywhere or any host where
you are not allowed to CREATE/DROP databases).

    python scripts/init_hosted.py
Reads RPMS_DB_HOST, RPMS_DB_USER, RPMS_DB_PASSWORD, RPMS_DB_NAME from the environment.
"""
import sys
from pathlib import Path

import mysql.connector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import DATABASE_DIR, load_db_config  # noqa: E402


def split_statements(sql: str):
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
            cursor.fetchall()
    conn.commit()
    cursor.close()
    print(f"Executed {path.name}")


def main() -> None:
    cfg = load_db_config()
    conn = mysql.connector.connect(host=cfg.host, port=cfg.port, user=cfg.user,
                                   password=cfg.password, database=cfg.database)
    try:
        run_script(conn, DATABASE_DIR / "hosted_schema.sql")
        run_script(conn, DATABASE_DIR / "hosted_sample_data.sql")
    finally:
        conn.close()
    print(f"Tables and demo data created in database '{cfg.database}'.")


if __name__ == "__main__":
    main()
