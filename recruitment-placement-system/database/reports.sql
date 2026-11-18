-- =========================================================
-- RPMS management reports (Database Design Specification, sections 26-27)
-- Each block starts with "-- name:" (key used by the application) and "-- title:".
-- Optional filters are bound as named parameters; NULL means "no filter".
-- =========================================================

-- name: dashboard_summary
-- title: Dashboard summary
SELECT
  (SELECT COUNT(*) FROM candidates) AS total_candidates,
  (SELECT COUNT(*) FROM candidates WHERE profile_status = 'ACTIVE') AS active_candidates,
  (SELECT COUNT(*) FROM companies WHERE status = 'ACTIVE') AS companies,
  (SELECT COUNT(*) FROM jobs WHERE status = 'OPEN') AS open_jobs,
  (SELECT COUNT(*) FROM applications) AS applications,
  (SELECT COUNT(*) FROM interview_rounds WHERE scheduled_date = CURDATE()) AS interviews_today,
  (SELECT COUNT(*) FROM applications WHERE application_status IN ('SELECTED','OFFERED','JOINED')) AS selected,
  (SELECT COUNT(*) FROM candidates WHERE placement_status = 'PLACED') AS placed;

-- name: candidates_by_technology
-- title: Candidate count by technology
SELECT COALESCE(primary_technology, 'Not set') AS technology,
       COUNT(*) AS candidates
FROM candidates
WHERE (%(passing_year)s IS NULL OR passing_year = %(passing_year)s)
GROUP BY primary_technology
ORDER BY candidates DESC, technology;

-- name: open_jobs_by_company
-- title: Open jobs by company
SELECT c.company_name,
       COUNT(j.job_id) AS open_jobs,
       COALESCE(SUM(j.openings), 0) AS total_openings
FROM jobs j
JOIN companies c ON c.company_id = j.company_id
WHERE j.status = 'OPEN'
  AND (%(company_id)s IS NULL OR j.company_id = %(company_id)s)
GROUP BY c.company_id, c.company_name
ORDER BY open_jobs DESC, c.company_name;

-- name: applications_by_status
-- title: Applications by status
SELECT application_status,
       COUNT(*) AS total
FROM applications
WHERE (%(date_from)s IS NULL OR DATE(applied_at) >= %(date_from)s)
  AND (%(date_to)s IS NULL OR DATE(applied_at) <= %(date_to)s)
GROUP BY application_status
ORDER BY total DESC;

-- name: recruitment_funnel
-- title: Recruitment funnel (cumulative stages)
SELECT COUNT(*) AS applications,
       COALESCE(SUM(CASE WHEN application_status IN ('SHORTLISTED','INTERVIEW_SCHEDULED','INTERVIEWED','SELECTED','OFFERED','JOINED') THEN 1 ELSE 0 END), 0) AS shortlisted,
       COALESCE(SUM(CASE WHEN application_status IN ('INTERVIEWED','SELECTED','OFFERED','JOINED') THEN 1 ELSE 0 END), 0) AS interviewed,
       COALESCE(SUM(CASE WHEN application_status IN ('SELECTED','OFFERED','JOINED') THEN 1 ELSE 0 END), 0) AS selected,
       COALESCE(SUM(CASE WHEN application_status = 'JOINED' THEN 1 ELSE 0 END), 0) AS joined
FROM applications
WHERE (%(date_from)s IS NULL OR DATE(applied_at) >= %(date_from)s)
  AND (%(date_to)s IS NULL OR DATE(applied_at) <= %(date_to)s);

-- name: company_wise_placements
-- title: Company-wise placements
SELECT c.company_name,
       COUNT(p.placement_id) AS placed_count
FROM placements p
JOIN companies c ON c.company_id = p.company_id
WHERE p.joining_status = 'JOINED'
  AND (%(company_id)s IS NULL OR p.company_id = %(company_id)s)
GROUP BY c.company_id, c.company_name
ORDER BY placed_count DESC, c.company_name;

-- name: technology_wise_placements
-- title: Technology-wise placements
SELECT COALESCE(c.primary_technology, 'Not set') AS technology,
       COUNT(p.placement_id) AS placed_count,
       ROUND(AVG(p.final_package_lpa), 2) AS avg_package_lpa
FROM placements p
JOIN candidates c ON c.candidate_id = p.candidate_id
WHERE p.joining_status = 'JOINED'
  AND (%(technology)s IS NULL OR c.primary_technology = %(technology)s)
GROUP BY c.primary_technology
ORDER BY placed_count DESC, technology;

-- name: recruiter_performance
-- title: Recruiter performance
SELECT u.full_name AS recruiter,
       COUNT(a.application_id) AS applications,
       SUM(CASE WHEN a.application_status IN ('SHORTLISTED','INTERVIEW_SCHEDULED','INTERVIEWED','SELECTED','OFFERED','JOINED') THEN 1 ELSE 0 END) AS shortlisted,
       SUM(CASE WHEN a.application_status = 'JOINED' THEN 1 ELSE 0 END) AS joined
FROM applications a
JOIN users u ON u.user_id = a.assigned_recruiter_id
WHERE (%(recruiter_id)s IS NULL OR a.assigned_recruiter_id = %(recruiter_id)s)
GROUP BY u.user_id, u.full_name
ORDER BY joined DESC, applications DESC;

-- name: pending_interviews
-- title: Pending interviews
SELECT ir.interview_id,
       a.application_code,
       c.full_name AS candidate,
       co.company_name,
       j.job_code,
       ir.round_number,
       ir.round_type,
       ir.scheduled_date,
       ir.scheduled_time,
       ir.mode,
       ir.status
FROM interview_rounds ir
JOIN applications a ON a.application_id = ir.application_id
JOIN candidates c ON c.candidate_id = a.candidate_id
JOIN jobs j ON j.job_id = a.job_id
JOIN companies co ON co.company_id = j.company_id
WHERE ir.status IN ('SCHEDULED', 'RESCHEDULED')
  AND ir.scheduled_date >= CURDATE()
ORDER BY ir.scheduled_date, ir.scheduled_time;

-- name: open_job_aging
-- title: Open job aging
SELECT j.job_code,
       j.job_title,
       co.company_name,
       j.location,
       j.posted_date,
       j.application_deadline,
       DATEDIFF(CURDATE(), j.posted_date) AS age_days,
       (SELECT COUNT(*) FROM applications a WHERE a.job_id = j.job_id) AS applications
FROM jobs j
JOIN companies co ON co.company_id = j.company_id
WHERE j.status = 'OPEN'
ORDER BY age_days DESC, j.job_code;

-- name: offer_to_joining_conversion
-- title: Offer-to-joining conversion
SELECT (SELECT COUNT(*) FROM offers) AS offers,
       (SELECT COUNT(*) FROM offers WHERE offer_status = 'ACCEPTED') AS accepted,
       (SELECT COUNT(*) FROM placements WHERE joining_status = 'JOINED') AS joined,
       ROUND(100.0 * (SELECT COUNT(*) FROM placements WHERE joining_status = 'JOINED')
             / NULLIF((SELECT COUNT(*) FROM offers), 0), 1) AS offer_to_join_pct;

-- name: placement_register
-- title: Placement register
SELECT p.placement_id,
       c.candidate_code,
       c.full_name AS candidate,
       co.company_name,
       j.job_code,
       p.designation,
       p.final_package_lpa,
       p.expected_joining_date,
       p.actual_joining_date,
       p.joining_status,
       p.placement_status
FROM placements p
JOIN candidates c ON c.candidate_id = p.candidate_id
JOIN companies co ON co.company_id = p.company_id
JOIN jobs j ON j.job_id = p.job_id
WHERE (%(company_id)s IS NULL OR p.company_id = %(company_id)s)
ORDER BY p.placement_id;

-- name: candidate_export
-- title: Candidate list export
SELECT candidate_code, full_name, email, mobile, qualification, passing_year, percentage,
       backlog_count, primary_technology, current_location, profile_status, placement_status
FROM candidates
WHERE (%(passing_year)s IS NULL OR passing_year = %(passing_year)s)
ORDER BY candidate_code;
