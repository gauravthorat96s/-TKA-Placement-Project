"""Test-only adapter. Runs the real service and repository code against SQLite, which lets the
workflow be exercised end to end without a MySQL server. MySQL-only syntax is translated here,
and values that SQLite returns as text are converted back to date/datetime objects on read."""
import datetime as dt
import re
import sqlite3
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

from app.exceptions import DatabaseError, DuplicateRecordError

DB_DIR = Path(__file__).resolve().parent.parent / "database"
DATE_COLS = {"date_of_birth", "posted_date", "application_deadline", "scheduled_date", "offer_date",
             "expected_joining_date", "actual_joining_date"}
DATETIME_COLS = {"applied_at", "changed_at", "logged_at", "created_at", "updated_at", "submitted_at", "last_login_at"}

sqlite3.register_adapter(dt.datetime, lambda v: v.isoformat(sep=" "))
sqlite3.register_adapter(dt.date, lambda v: v.isoformat())
sqlite3.register_adapter(Decimal, float)


def schema_to_sqlite(sql: str) -> str:
    sql = re.sub(r"^(DROP DATABASE|CREATE DATABASE|USE) .*$", "", sql, flags=re.M)
    sql = re.sub(r"^\s*CHARACTER SET.*$|^\s*COLLATE .*$|^SET FOREIGN_KEY_CHECKS.*$", "", sql, flags=re.M)
    sql = re.sub(r"\b(INT|BIGINT) PRIMARY KEY AUTO_INCREMENT", "INTEGER PRIMARY KEY AUTOINCREMENT", sql)
    sql = sql.replace("ON UPDATE CURRENT_TIMESTAMP", "")
    sql = re.sub(r"DATE_ADD\('([^']+)',\s*INTERVAL (\d+) DAY\)", r"datetime('\1', '+\2 day')", sql)
    return sql


def _translate(sql: str, params) -> str:
    if isinstance(params, dict):
        sql = re.sub(r"%\((\w+)\)s", r":\1", sql)
    else:
        sql = sql.replace("%s", "?")
    sql = re.sub(r"DATEDIFF\(([^,]+),\s*([^)]+)\)", r"(julianday(\1) - julianday(\2))", sql)
    return sql.replace("CURDATE()", "date('now')")


def _convert(name, value):
    if value is None or not isinstance(value, str):
        return value
    if name in DATE_COLS:
        return dt.date.fromisoformat(value[:10])
    if name in DATETIME_COLS:
        return dt.datetime.fromisoformat(value)
    return value


class _Cursor:
    def __init__(self, conn):
        self._cur = conn.cursor()
        self.lastrowid = None
        self.rowcount = 0

    def execute(self, sql, params=None):
        if isinstance(params, list):
            params = tuple(params)
        self._cur.execute(_translate(sql, params), params or ())
        self.lastrowid = self._cur.lastrowid
        self.rowcount = self._cur.rowcount

    def _row(self, row):
        names = [d[0] for d in self._cur.description]
        return {n: _convert(n, v) for n, v in zip(names, row)}

    def fetchone(self):
        row = self._cur.fetchone()
        return None if row is None else self._row(row)

    def fetchall(self):
        return [self._row(r) for r in self._cur.fetchall()]


class SQLiteDatabase:
    """Drop-in replacement for app.db.connection.Database."""

    def __init__(self):
        self.conn = sqlite3.connect(":memory:", isolation_level=None)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(schema_to_sqlite((DB_DIR / "database_schema.sql").read_text(encoding="utf-8")))
        self.conn.executescript(schema_to_sqlite((DB_DIR / "sample_data.sql").read_text(encoding="utf-8")))

    @contextmanager
    def cursor(self):
        yield _Cursor(self.conn)

    @contextmanager
    def transaction(self):
        self.conn.execute("BEGIN")
        try:
            yield _Cursor(self.conn)
            self.conn.execute("COMMIT")
        except sqlite3.IntegrityError as exc:
            self.conn.execute("ROLLBACK")
            if "UNIQUE" in str(exc):
                raise DuplicateRecordError("This record already exists (duplicate value).") from exc
            raise DatabaseError(f"Transaction rolled back: {exc}") from exc
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise

    def scalar(self, sql, params=()):
        return self.conn.execute(_translate(sql, params), params).fetchone()[0]
