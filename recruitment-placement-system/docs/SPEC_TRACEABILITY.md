# Specification Traceability

| Requirement (source) | Where it is implemented |
|---|---|
| Candidate Eligibility Engine: qualification, percentage, passing year, technology/skills, backlogs, job status (Project Abstract) | `app/services/eligibility_engine.py`, used by `ApplicationService.apply()` and `check_eligibility()` |
| Stages: Registration -> Eligibility -> Application -> Shortlisting -> Interview -> Feedback -> Selection -> Offer -> Joining -> Placement (Abstract) | `services/application_service.py`, `interview_service.py`, `placement_service.py`, `services/workflow.py` |
| Duplicate application prevention (Abstract, DB 22, 29) | `ApplicationService.apply()` pre-check, plus UNIQUE(candidate_id, job_id) in the schema |
| Candidate email/mobile uniqueness (DB 20, 29) | `CandidateService.register()` / `update()` pre-check, plus UNIQUE columns |
| Interview round uniqueness and one feedback per round (DB 22, 29) | `interview_rounds` UNIQUE(application_id, round_number); `interview_feedback` UNIQUE(interview_id) |
| Historical records never hard deleted (DB 22, 23) | Candidates and companies are soft-deactivated; `application_history` is append-only |
| Transactions for multi-table operations; rollback demonstration (DB 28, 32, 33) | `db/connection.py` `Database.transaction()`; `PlacementService.confirm_joining()`; `scripts/demo_rollback.py` |
| Parameterized SQL only (DB 2, 32) | Every repository query binds values with `%s`; identifiers come from code constants |
| Passwords never stored in plain text (DB 6, 32) | `app/utils/security.py` (PBKDF2-SHA256) |
| Management reports: all 10 required queries, plus dashboard, placement register and candidate export (DB 26, 27) | `database/reports.sql`, run by `services/report_service.py` |
| Role-based access: Admin, Recruiter, Placement Officer (UI 5.1) | `services/authorization.py`, enforced inside every write service |
| Validation messages (UI 8) | `validation/validators.py`, exact wording; tested in `tests/test_validators.py` |
| Status values match the spec (DB 21, UI 7) | `models/enums.py`; enforced by CHECK constraints in the schema |
| 12 HTML prototype pages, shared CSS, relative links, no backend terms (UI 1-4, 10-11) | `prototype-ui/` (generated); link check and wording check run during build |
| Modular architecture: models, DB operations, services, validations, utilities, reports, application flow (Abstract) | `app/models`, `app/db`, `app/services`, `app/validation`, `app/utils`, `app/services/report_service.py`, `app/cli` |
