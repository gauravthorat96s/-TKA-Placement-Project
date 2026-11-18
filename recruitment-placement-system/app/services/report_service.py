"""Management reports. Each report is a named, parameterized query stored in database/reports.sql."""
from pathlib import Path

from app.config import REPORTS_SQL
from app.db.connection import Database
from app.db.repositories import fetch_all, fetch_one
from app.exceptions import NotFoundError
from app.utils.file_io import write_csv

REPORT_PARAMETERS = ("date_from", "date_to", "technology", "company_id", "recruiter_id", "passing_year")


def load_named_queries(path=REPORTS_SQL) -> dict:
    """Parse blocks that start with '-- name: <key>' and an optional '-- title: <text>' line."""
    queries, name, title, lines = {}, None, None, []

    def close_block():
        if name:
            queries[name] = {"title": title or name, "sql": "\n".join(lines).strip()}

    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        if raw.startswith("-- name:"):
            close_block()
            name, title, lines = raw.split(":", 1)[1].strip(), None, []
        elif raw.startswith("-- title:") and name and not lines:
            title = raw.split(":", 1)[1].strip()
        elif name:
            lines.append(raw)
    close_block()
    return queries


class ReportService:
    def __init__(self, db: Database, sql_path=REPORTS_SQL):
        self.db = db
        self.queries = load_named_queries(sql_path)

    def available(self):
        return [(name, meta["title"]) for name, meta in self.queries.items()]

    def run(self, name: str, filters: dict = None):
        if name not in self.queries:
            raise NotFoundError(f"Unknown report: {name}")
        params = {key: None for key in REPORT_PARAMETERS}
        params.update({k: v for k, v in (filters or {}).items() if v not in (None, "")})
        with self.db.cursor() as cur:
            return fetch_all(cur, self.queries[name]["sql"], params)

    def dashboard(self) -> dict:
        with self.db.cursor() as cur:
            return fetch_one(cur, self.queries["dashboard_summary"]["sql"], {key: None for key in REPORT_PARAMETERS})

    def export_csv(self, name: str, path, filters: dict = None) -> int:
        return write_csv(path, self.run(name, filters))
