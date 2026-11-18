# Entity-Relationship Diagram

Source of truth: `database/database_schema.sql` (17 tables, Database Design Specification sections 3-4).

```mermaid
erDiagram
    roles ||--o{ users : "assigned to"
    users ||--o{ jobs : "created_by"
    users ||--o{ applications : "assigned_recruiter_id"
    users ||--o{ application_history : "changed_by"
    users ||--o{ interview_feedback : "submitted_by"
    users ||--o{ activity_logs : "actor"

    candidates ||--o{ candidate_skills : "has"
    skills ||--o{ candidate_skills : "mapped in"
    skills ||--o{ job_skills : "required by"
    companies ||--o{ jobs : "posts"
    jobs ||--o{ job_skills : "requires"
    candidates ||--o{ applications : "applies"
    jobs ||--o{ applications : "receives"
    applications ||--o{ application_history : "audit trail"
    applications ||--o{ interview_rounds : "has rounds"
    interview_rounds ||--o| interview_feedback : "one feedback"
    applications ||--o| offers : "at most one offer"
    offers ||--o| placements : "at most one placement"
    candidates ||--o{ placements : "placed as"
    companies ||--o{ placements : "hires"
    jobs ||--o{ placements : "fills"
```

Key constraints: `applications` is UNIQUE on (candidate_id, job_id); `interview_rounds` is UNIQUE on (application_id, round_number); `interview_feedback.interview_id` and `offers.application_id` are UNIQUE; `candidates.email` and `candidates.mobile` are UNIQUE; percentages are CHECKed to 0-100.
