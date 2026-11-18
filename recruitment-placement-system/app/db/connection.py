"""Connection handling and transaction boundaries.

Services use db.transaction() for any write (commit on success, rollback on any error)
and db.cursor() for read-only queries.
"""
from contextlib import contextmanager

from app.config import DBConfig
from app.exceptions import DatabaseError, DuplicateRecordError

try:  # The driver is needed only when a connection is opened, so rules and tests run without it.
    import mysql.connector as mysql_connector
    from mysql.connector import Error as MySQLError
except ImportError:  # pragma: no cover - exercised only when the driver is missing
    mysql_connector = None

    class MySQLError(Exception):
        errno = None
        msg = ""

DUPLICATE_KEY_ERRNO = 1062


class Database:
    def __init__(self, config: DBConfig):
        self._config = config

    def _connect(self):
        if mysql_connector is None:
            raise DatabaseError("mysql-connector-python is not installed. Run: pip install -r requirements.txt")
        cfg = self._config
        try:
            return mysql_connector.connect(
                host=cfg.host, port=cfg.port, user=cfg.user,
                password=cfg.password, database=cfg.database, autocommit=False,
            )
        except MySQLError as exc:
            raise DatabaseError(f"Could not connect to MySQL: {exc.msg}") from exc

    @contextmanager
    def cursor(self):
        """Read-only cursor returning dict rows."""
        conn = self._connect()
        cur = conn.cursor(dictionary=True)
        try:
            yield cur
        except MySQLError as exc:
            raise DatabaseError(f"Query failed: {exc.msg}") from exc
        finally:
            cur.close()
            conn.close()

    @contextmanager
    def transaction(self):
        """All-or-nothing unit of work. Any exception rolls back every change in the block."""
        conn = self._connect()
        cur = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()
            yield cur
            conn.commit()
        except MySQLError as exc:
            conn.rollback()
            if exc.errno == DUPLICATE_KEY_ERRNO:
                raise DuplicateRecordError("This record already exists (duplicate value).") from exc
            raise DatabaseError(f"Transaction rolled back: {exc.msg}") from exc
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
