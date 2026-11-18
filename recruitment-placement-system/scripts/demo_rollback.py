"""Demonstrates the transaction rollback rule (Database Design spec, sections 28 and 33).

Confirming a joining writes a placement row first, then fails on purpose. The rollback must
leave no placement row, the candidate unchanged, and the application unchanged.

    python scripts/demo_rollback.py   (requires an initialised database)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import load_db_config  # noqa: E402
from app.db.connection import Database  # noqa: E402
from app.exceptions import DatabaseError  # noqa: E402
from app.services.container import Services  # noqa: E402
from app.utils.logger import setup_logging  # noqa: E402

OFFER_ID = 5  # ACCEPTED offer in the sample data with no placement yet


def snapshot(db: Database):
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM placements WHERE offer_id = %s", (OFFER_ID,))
        placements = cur.fetchone()["n"]
        cur.execute("SELECT c.placement_status, a.application_status FROM offers o "
                    "JOIN applications a ON a.application_id = o.application_id "
                    "JOIN candidates c ON c.candidate_id = a.candidate_id WHERE o.offer_id = %s", (OFFER_ID,))
        row = cur.fetchone()
    return {"placements_for_offer": placements, "candidate": row["placement_status"], "application": row["application_status"]}


def main() -> None:
    setup_logging()
    db = Database(load_db_config())
    services = Services(db)
    user = services.auth.login("neha.placement", "Demo@123")

    before = snapshot(db)
    print("Before:", before)
    try:
        services.placements.confirm_joining(user, OFFER_ID, "JOINED", "2026-10-29", simulate_failure=True)
    except DatabaseError as exc:
        print("Operation failed as intended:", exc)
    after = snapshot(db)
    print("After: ", after)
    print("ROLLBACK VERIFIED" if before == after else "ROLLBACK FAILED - data changed")


if __name__ == "__main__":
    main()
