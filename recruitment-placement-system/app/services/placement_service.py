"""Offers and placements: SELECTED -> offer -> acceptance -> joining confirmation -> PLACED.

Every multi-table step runs inside one transaction, so a failure leaves no partial data.
"""
from app.db.connection import Database
from app.db.repositories import ApplicationRepository, CandidateRepository, JobRepository, OfferRepository
from app.exceptions import DatabaseError, DuplicateRecordError, NotFoundError, ValidationError, WorkflowError
from app.models.enums import JOINING_STATUS, OFFER_STATUS
from app.services.authorization import require
from app.services.common import audit, get_application, transition_application
from app.services.workflow import OFFER_EFFECT_ON_APPLICATION, OFFER_TRANSITIONS
from app.validation.validators import (
    choice, optional_text, parse_date, parse_decimal, require_text,
)

FINAL_JOINING_OUTCOMES = ("NOT_JOINED", "NO_SHOW")
CONFIRMABLE_JOINING = ("JOINED", "NOT_JOINED", "DEFERRED", "NO_SHOW")


class PlacementService:
    def __init__(self, db: Database):
        self.db = db
        self.apps = ApplicationRepository()
        self.offers = OfferRepository()
        self.jobs = JobRepository()
        self.candidates = CandidateRepository()

    def create_offer(self, actor, application_id: int, designation: str, package_lpa, offer_date,
                     expected_joining_date=None, remarks: str = None) -> str:
        require(actor, "offer:write")
        designation = require_text(designation, "Please enter the offered designation.")
        package = parse_decimal(package_lpa, "Offered package", required=True)
        if package <= 0:
            raise ValidationError("Offered package must be greater than zero.")
        offered_on = parse_date(offer_date, "Offer date", required=True)
        joining = parse_date(expected_joining_date, "Expected joining date")
        with self.db.transaction() as cur:
            app = get_application(cur, application_id)
            if app["application_status"] != "SELECTED":
                raise WorkflowError("Offers can only be created for SELECTED applications.")
            if self.offers.by_application(cur, application_id):
                raise DuplicateRecordError("An offer already exists for this application.")
            code = f"OFF-{offered_on.year}-{self.offers.next_id(cur):03d}"
            self.offers.insert_offer(cur, {
                "offer_code": code, "application_id": application_id, "designation": designation,
                "offered_package_lpa": package, "offer_date": offered_on,
                "expected_joining_date": joining, "offer_status": "OFFERED",
                "remarks": optional_text(remarks),
            })
            transition_application(cur, app, "OFFERED", actor, f"Offer {code} issued")
            audit(cur, actor, "OFFER", "CREATE", code, f"Offer {designation} at {package} LPA")
        return code

    def update_offer_status(self, actor, offer_id: int, new_status: str, remarks: str = None) -> None:
        require(actor, "offer:write")
        new_status = choice(new_status, OFFER_STATUS, "Offer status")
        with self.db.transaction() as cur:
            offer = self._offer(cur, offer_id)
            old = offer["offer_status"]
            if new_status not in OFFER_TRANSITIONS.get(old, set()):
                raise WorkflowError(f"Offer cannot move from {old} to {new_status}.")
            self.offers.update_offer(cur, offer_id, {"offer_status": new_status,
                                                     "remarks": optional_text(remarks) or offer["remarks"]})
            effect = OFFER_EFFECT_ON_APPLICATION.get(new_status)
            if effect:
                app = get_application(cur, offer["application_id"])
                transition_application(cur, app, effect, actor, f"Offer {new_status.lower()}")
            audit(cur, actor, "OFFER", new_status, offer["offer_code"], f"{old} -> {new_status}")

    def confirm_joining(self, actor, offer_id: int, joining_status: str, actual_joining_date=None,
                        simulate_failure: bool = False) -> int:
        """Create (or update) the placement record and move the candidate and application to match."""
        require(actor, "offer:write")
        joining_status = choice(joining_status, CONFIRMABLE_JOINING, "Joining status")
        actual = parse_date(actual_joining_date, "Actual joining date")
        if joining_status == "JOINED" and actual is None:
            raise ValidationError("Actual joining date is required when joining is confirmed.")
        with self.db.transaction() as cur:
            offer = self._offer(cur, offer_id)
            if offer["offer_status"] != "ACCEPTED":
                raise WorkflowError("Offer must be ACCEPTED before joining can be confirmed.")
            app = get_application(cur, offer["application_id"])
            job = self.jobs.get(cur, app["job_id"])
            values = {"joining_status": joining_status, "actual_joining_date": actual, "placement_status": "ACTIVE"}

            existing = self.offers.placement_by_offer(cur, offer_id)
            if existing:
                if existing["joining_status"] == "JOINED":
                    raise DuplicateRecordError("Joining is already confirmed for this offer.")
                if existing["joining_status"] in FINAL_JOINING_OUTCOMES:
                    raise WorkflowError("This joining outcome is final and cannot be changed.")
                self.offers.update_placement(cur, existing["placement_id"], values)
                placement_id = existing["placement_id"]
            else:
                placement_id = self.offers.insert_placement(cur, {
                    "candidate_id": app["candidate_id"], "company_id": job["company_id"],
                    "job_id": app["job_id"], "offer_id": offer_id, "designation": offer["designation"],
                    "final_package_lpa": offer["offered_package_lpa"],
                    "expected_joining_date": offer["expected_joining_date"], **values,
                })

            if simulate_failure:
                # Raised after the first write on purpose: the transaction must roll the placement back.
                raise DatabaseError("Simulated failure after placement insert (rollback demonstration).")

            if joining_status == "JOINED":
                self.candidates.set_placement_status(cur, app["candidate_id"], "PLACED")
                transition_application(cur, app, "JOINED", actor, "Candidate joined")
            elif joining_status in FINAL_JOINING_OUTCOMES:
                transition_application(cur, app, "WITHDRAWN", actor, f"Joining outcome: {joining_status}")
            audit(cur, actor, "PLACEMENT", joining_status, offer["offer_code"], f"Joining {joining_status}")
        return placement_id

    def _offer(self, cur, offer_id):
        offer = self.offers.get_offer(cur, offer_id)
        if not offer:
            raise NotFoundError("Offer not found.")
        return offer

    def list_offers(self, filters: dict):
        with self.db.cursor() as cur:
            return self.offers.search_offers(cur, filters)

    def list_placements(self, filters: dict):
        with self.db.cursor() as cur:
            return self.offers.search_placements(cur, filters)
