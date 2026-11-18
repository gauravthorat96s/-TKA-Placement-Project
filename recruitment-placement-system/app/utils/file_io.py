"""File handling: CSV import (bulk candidate upload) and CSV export (report downloads)."""
import csv
from pathlib import Path
from typing import Iterable, List, Optional

from app.exceptions import ValidationError


def write_csv(path, rows: Iterable[dict], columns: Optional[List[str]] = None) -> int:
    rows = list(rows)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if columns is None:
        columns = list(rows[0].keys()) if rows else []
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)


def read_csv(path) -> List[dict]:
    source = Path(path)
    if not source.exists():
        raise ValidationError(f"File not found: {source}")
    with source.open(newline="", encoding="utf-8-sig") as handle:
        return [{(key or "").strip(): (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]
