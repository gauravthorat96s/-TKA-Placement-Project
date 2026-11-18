# Sample Data Revisions

The supplied `rpms_sample_data.sql` was checked against the Database Design Specification. This file records what was changed and why. The original schema was kept as supplied, with the file renamed to `database_schema.sql`.

## Counts against the specification minimums (section 24)

| Entity | Supplied | Revised | Minimum |
|---|---|---|---|
| Roles | 3 | 3 | 3 |
| Users | 5 | 5 | 5 |
| Candidates | 20 | **30** | 30 |
| Skills | 10 | 10 | 10 |
| Companies | 8 | 8 | 8 |
| Jobs | 12 | 12 | 12 |
| Applications | 40 | **50** | 40-50 |
| Interview rounds | 20 | **23** | 20+ |
| Feedback | 15 | **17** | 15+ |
| Offers | 6 | **8** | 8+ |
| Placements | 3 | **5** | 5+ |

## Corrections

1. **Password hashes.** The supplied hashes were placeholders (`$2y$10$DEMO_..._HASH_ONLY`) and could not be verified. Every demo account now uses PBKDF2-SHA256 hashes for the password `Demo@123`. These are demo credentials only.
2. **Application status out of step with placements and offers.** Three applications with a joined placement were still `OFFERED` and are now `JOINED` (applications 5, 13, 21). Three `SELECTED` applications with an offer were moved to `OFFERED` (applications 4, 12, 28), following the workflow rule that offer creation moves SELECTED to OFFERED. History rows record each change.
3. **New candidates 21-30** were added with skills, qualifications and locations. Each has one application (applications 41-50). Eligibility and status for each new application were computed by the project's own Candidate Eligibility Engine, so the data follows the same rules the application enforces. Rejected applications (43, 46) are the ones that fail a rule.
4. **Support rows for the new applications:** interview rounds 21-23 and feedback 16-17, so that INTERVIEWED, SCHEDULED and SELECTED statuses have matching interview records.
5. **New offers 7-8 and placements 4-5** (both pending joining), so the offer and placement reports show more than the original three placements.
6. **Application history** rows were added for the new applications and for each status change above.

## Intentional state for the rollback demonstration

Offer 5 (application 4) is `ACCEPTED` with no placement record. `scripts/demo_rollback.py` uses it to show that a failed joining confirmation leaves no partial data. It is a valid "accepted, joining pending" state, not an error.

## Known differences between the specifications

- The UI specification's example codes (CAN1001, APP1001, COM101, Infosys) differ from the database design codes (CAN-2026-0001, APP-2026-0001, COM-001). The database design was followed, and the prototype shows the same data as the database.
- Application statuses in the UI specification (Applied, Eligible, Shortlisted, Selected, Rejected) are simplified. The database design status list (section 21) was used throughout.
- The UI specification lists job status as DRAFT/OPEN/CLOSED. The database design also has CANCELLED, which is included.
- The UI specification's example "Offer-to-Join 83.3%" is a sample figure. The report computes joined / offers issued, which gives 37.5% for this data.
