"""Database operations (repository layer).

Every method receives an open cursor from the service layer, so the service decides the
transaction boundary. Values always travel as %s / %(name)s parameters. Table and column
names used in SQL text are constants defined in this module, never user input.
"""
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- helpers
def insert_row(cur, table: str, data: Dict[str, Any]) -> int:
    columns = ", ".join(data.keys())
    placeholders = ", ".join(["%s"] * len(data))
    cur.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(data.values()))
    return cur.lastrowid


def update_row(cur, table: str, pk: str, pk_value, data: Dict[str, Any]) -> int:
    assignments = ", ".join(f"{column} = %s" for column in data)
    cur.execute(f"UPDATE {table} SET {assignments} WHERE {pk} = %s", (*data.values(), pk_value))
    return cur.rowcount


def fetch_one(cur, sql: str, params=None) -> Optional[dict]:
    cur.execute(sql, params)
    return cur.fetchone()


def fetch_all(cur, sql: str, params=None) -> List[dict]:
    cur.execute(sql, params)
    return cur.fetchall()


def next_id(cur, table: str, pk: str) -> int:
    row = fetch_one(cur, f"SELECT COALESCE(MAX({pk}), 0) + 1 AS next_value FROM {table}")
    return int(row["next_value"])


def _where(filters_spec, filters) -> (str, list):
    """Build a WHERE fragment from {key: (sql_column, mode)} where mode is 'like' or 'eq'."""
    clauses, params = [], []
    for key, (column, mode) in filters_spec.items():
        value = filters.get(key)
        if value in (None, ""):
            continue
        if mode == "like":
            clauses.append(f"{column} LIKE %s")
            params.append(f"%{value}%")
        elif mode == "gte":
            clauses.append(f"{column} >= %s")
            params.append(value)
        elif mode == "lte":
            clauses.append(f"{column} <= %s")
            params.append(value)
        else:
            clauses.append(f"{column} = %s")
            params.append(value)
    return (" AND ".join(clauses) or "1 = 1"), params


# --------------------------------------------------------------------------- users
class UserRepository:
    def get_by_username(self, cur, username: str):
        return fetch_one(cur, """SELECT u.*, r.role_code, r.role_name
                                 FROM users u JOIN roles r ON r.role_id = u.role_id
                                 WHERE u.username = %s""", (username,))

    def touch_login(self, cur, user_id: int):
        update_row(cur, "users", "user_id", user_id, {"last_login_at": _now()})

    def insert_activity(self, cur, user_id, module, action, record_id, description):
        insert_row(cur, "activity_logs", {
            "user_id": user_id, "module_name": module, "action_name": action,
            "record_id": record_id, "description": description,
        })


def _now():
    from datetime import datetime
    return datetime.now().replace(microsecond=0)


# --------------------------------------------------------------------------- skills
class SkillRepository:
    def get(self, cur, skill_id: int):
        return fetch_one(cur, "SELECT * FROM skills WHERE skill_id = %s", (skill_id,))

    def list_active(self, cur):
        return fetch_all(cur, "SELECT skill_id, skill_name, category FROM skills WHERE is_active = 1 ORDER BY skill_name")


# --------------------------------------------------------------------------- candidates
class CandidateRepository:
    def insert(self, cur, data):
        return insert_row(cur, "candidates", data)

    def update(self, cur, candidate_id, data):
        return update_row(cur, "candidates", "candidate_id", candidate_id, data)

    def get(self, cur, candidate_id):
        return fetch_one(cur, "SELECT * FROM candidates WHERE candidate_id = %s", (candidate_id,))

    def find_duplicate(self, cur, email, mobile, exclude_id=None):
        return fetch_one(cur, """SELECT candidate_id FROM candidates
                                 WHERE (email = %s OR mobile = %s) AND candidate_id <> %s""",
                         (email, mobile, exclude_id or 0))

    def next_id(self, cur):
        return next_id(cur, "candidates", "candidate_id")

    def set_placement_status(self, cur, candidate_id, status):
        return update_row(cur, "candidates", "candidate_id", candidate_id, {"placement_status": status})

    def search(self, cur, filters: dict, limit: int = 50):
        where, params = _where({
            "candidate_code": ("c.candidate_code", "like"),
            "full_name": ("c.full_name", "like"),
            "mobile": ("c.mobile", "like"),
            "email": ("c.email", "like"),
            "primary_technology": ("c.primary_technology", "eq"),
            "passing_year": ("c.passing_year", "eq"),
            "qualification": ("c.qualification", "eq"),
            "placement_status": ("c.placement_status", "eq"),
            "profile_status": ("c.profile_status", "eq"),
        }, filters)
        sql = f"""SELECT c.candidate_id, c.candidate_code, c.full_name, c.email, c.mobile,
                         c.qualification, c.passing_year, c.percentage, c.backlog_count,
                         c.primary_technology, c.profile_status, c.placement_status
                  FROM candidates c
                  WHERE {where}
                  ORDER BY c.candidate_code
                  LIMIT %s"""
        return fetch_all(cur, sql, params + [limit])

    def replace_skills(self, cur, candidate_id: int, skills: List[dict]):
        cur.execute("DELETE FROM candidate_skills WHERE candidate_id = %s", (candidate_id,))
        for skill in skills:
            insert_row(cur, "candidate_skills", {
                "candidate_id": candidate_id,
                "skill_id": skill["skill_id"],
                "proficiency_level": skill.get("proficiency_level"),
                "years_experience": skill.get("years_experience", 0),
                "is_primary": 1 if skill.get("is_primary") else 0,
            })

    def skills(self, cur, candidate_id: int):
        return fetch_all(cur, """SELECT cs.candidate_id, cs.skill_id, s.skill_name,
                                        cs.proficiency_level, cs.years_experience, cs.is_primary
                                 FROM candidate_skills cs JOIN skills s ON s.skill_id = cs.skill_id
                                 WHERE cs.candidate_id = %s ORDER BY s.skill_name""", (candidate_id,))


# --------------------------------------------------------------------------- companies & jobs
class CompanyRepository:
    def insert(self, cur, data):
        return insert_row(cur, "companies", data)

    def update(self, cur, company_id, data):
        return update_row(cur, "companies", "company_id", company_id, data)

    def get(self, cur, company_id):
        return fetch_one(cur, "SELECT * FROM companies WHERE company_id = %s", (company_id,))

    def next_id(self, cur):
        return next_id(cur, "companies", "company_id")

    def search(self, cur, filters: dict, limit: int = 100):
        where, params = _where({
            "company_name": ("c.company_name", "like"),
            "status": ("c.status", "eq"),
        }, filters)
        return fetch_all(cur, f"""SELECT c.company_id, c.company_code, c.company_name, c.industry,
                                         c.location, c.company_type, c.hr_name, c.hr_email, c.status,
                                         (SELECT COUNT(*) FROM jobs j WHERE j.company_id = c.company_id
                                            AND j.status = 'OPEN') AS open_jobs
                                  FROM companies c WHERE {where} ORDER BY c.company_name LIMIT %s""",
                         params + [limit])


class JobRepository:
    def insert(self, cur, data):
        return insert_row(cur, "jobs", data)

    def update(self, cur, job_id, data):
        return update_row(cur, "jobs", "job_id", job_id, data)

    def get(self, cur, job_id):
        return fetch_one(cur, "SELECT * FROM jobs WHERE job_id = %s", (job_id,))

    def next_id(self, cur):
        return next_id(cur, "jobs", "job_id")

    def application_count(self, cur, job_id):
        row = fetch_one(cur, "SELECT COUNT(*) AS total FROM applications WHERE job_id = %s", (job_id,))
        return int(row["total"])

    def replace_skills(self, cur, job_id: int, skills: List[dict]):
        cur.execute("DELETE FROM job_skills WHERE job_id = %s", (job_id,))
        for skill in skills:
            insert_row(cur, "job_skills", {
                "job_id": job_id,
                "skill_id": skill["skill_id"],
                "minimum_level": skill.get("minimum_level"),
                "mandatory_flag": 1 if skill.get("mandatory_flag", True) else 0,
            })

    def skills(self, cur, job_id: int):
        return fetch_all(cur, """SELECT js.job_id, js.skill_id, s.skill_name, js.minimum_level, js.mandatory_flag
                                 FROM job_skills js JOIN skills s ON s.skill_id = js.skill_id
                                 WHERE js.job_id = %s ORDER BY s.skill_name""", (job_id,))

    def search(self, cur, filters: dict, limit: int = 100):
        where, params = _where({
            "job_code": ("j.job_code", "like"),
            "company_id": ("j.company_id", "eq"),
            "status": ("j.status", "eq"),
            "employment_type": ("j.employment_type", "eq"),
            "location": ("j.location", "like"),
        }, filters)
        tech = filters.get("technology")
        if tech:
            where += (" AND EXISTS (SELECT 1 FROM job_skills js JOIN skills s ON s.skill_id = js.skill_id"
                      " WHERE js.job_id = j.job_id AND s.skill_name = %s)")
            params.append(tech)
        return fetch_all(cur, f"""SELECT j.job_id, j.job_code, co.company_id, co.company_name, j.job_title,
                                         j.employment_type, j.location, j.openings, j.application_deadline,
                                         j.status,
                                         (SELECT COUNT(*) FROM applications a WHERE a.job_id = j.job_id) AS applications
                                  FROM jobs j JOIN companies co ON co.company_id = j.company_id
                                  WHERE {where} ORDER BY j.job_code LIMIT %s""", params + [limit])


# --------------------------------------------------------------------------- applications
class ApplicationRepository:
    def insert(self, cur, data):
        return insert_row(cur, "applications", data)

    def get(self, cur, application_id):
        return fetch_one(cur, "SELECT * FROM applications WHERE application_id = %s", (application_id,))

    def find_by_candidate_job(self, cur, candidate_id, job_id):
        return fetch_one(cur, "SELECT application_id FROM applications WHERE candidate_id = %s AND job_id = %s",
                         (candidate_id, job_id))

    def next_id(self, cur):
        return next_id(cur, "applications", "application_id")

    def update_status(self, cur, application_id, status):
        return update_row(cur, "applications", "application_id", application_id, {"application_status": status})

    def update_eligibility(self, cur, application_id, eligibility_status, reason):
        return update_row(cur, "applications", "application_id", application_id,
                          {"eligibility_status": eligibility_status, "eligibility_reason": reason[:500]})

    def insert_history(self, cur, application_id, old_status, new_status, remarks, changed_by):
        insert_row(cur, "application_history", {
            "application_id": application_id, "old_status": old_status, "new_status": new_status,
            "remarks": (remarks or None) and remarks[:500], "changed_by": changed_by,
        })

    def history(self, cur, application_id):
        return fetch_all(cur, """SELECT h.old_status, h.new_status, h.remarks, h.changed_at,
                                        u.full_name AS changed_by
                                 FROM application_history h JOIN users u ON u.user_id = h.changed_by
                                 WHERE h.application_id = %s ORDER BY h.changed_at, h.history_id""",
                         (application_id,))

    def search(self, cur, filters: dict, limit: int = 100):
        where, params = _where({
            "application_status": ("a.application_status", "eq"),
            "eligibility_status": ("a.eligibility_status", "eq"),
            "job_id": ("a.job_id", "eq"),
            "candidate_id": ("a.candidate_id", "eq"),
            "company_id": ("j.company_id", "eq"),
            "recruiter_id": ("a.assigned_recruiter_id", "eq"),
            "date_from": ("DATE(a.applied_at)", "gte"),
            "date_to": ("DATE(a.applied_at)", "lte"),
        }, filters)
        return fetch_all(cur, f"""SELECT a.application_id, a.application_code, c.candidate_id, c.candidate_code,
                                         c.full_name AS candidate, co.company_name, j.job_code, j.job_title,
                                         a.eligibility_status, a.application_status, a.applied_at,
                                         u.full_name AS recruiter
                                  FROM applications a
                                  JOIN candidates c ON c.candidate_id = a.candidate_id
                                  JOIN jobs j ON j.job_id = a.job_id
                                  JOIN companies co ON co.company_id = j.company_id
                                  LEFT JOIN users u ON u.user_id = a.assigned_recruiter_id
                                  WHERE {where} ORDER BY a.applied_at DESC, a.application_id DESC LIMIT %s""",
                         params + [limit])


# --------------------------------------------------------------------------- interviews
class InterviewRepository:
    def insert(self, cur, data):
        return insert_row(cur, "interview_rounds", data)

    def get(self, cur, interview_id):
        return fetch_one(cur, "SELECT * FROM interview_rounds WHERE interview_id = %s", (interview_id,))

    def update(self, cur, interview_id, data):
        return update_row(cur, "interview_rounds", "interview_id", interview_id, data)

    def max_round(self, cur, application_id) -> int:
        row = fetch_one(cur, "SELECT COALESCE(MAX(round_number), 0) AS m FROM interview_rounds WHERE application_id = %s",
                        (application_id,))
        return int(row["m"])

    def feedback_for(self, cur, interview_id):
        return fetch_one(cur, "SELECT * FROM interview_feedback WHERE interview_id = %s", (interview_id,))

    def insert_feedback(self, cur, data):
        return insert_row(cur, "interview_feedback", data)

    def search(self, cur, filters: dict, limit: int = 100):
        where, params = _where({
            "status": ("ir.status", "eq"),
            "application_id": ("ir.application_id", "eq"),
            "date_from": ("ir.scheduled_date", "gte"),
            "date_to": ("ir.scheduled_date", "lte"),
        }, filters)
        if filters.get("pending_only"):
            where += " AND ir.status IN ('SCHEDULED', 'RESCHEDULED')"
        return fetch_all(cur, f"""SELECT ir.interview_id, a.application_code, c.candidate_code,
                                         c.full_name AS candidate, co.company_name, j.job_code,
                                         ir.round_number, ir.round_type, ir.scheduled_date,
                                         ir.scheduled_time, ir.mode, ir.interviewer_name, ir.status
                                  FROM interview_rounds ir
                                  JOIN applications a ON a.application_id = ir.application_id
                                  JOIN candidates c ON c.candidate_id = a.candidate_id
                                  JOIN jobs j ON j.job_id = a.job_id
                                  JOIN companies co ON co.company_id = j.company_id
                                  WHERE {where} ORDER BY ir.scheduled_date, ir.scheduled_time LIMIT %s""",
                         params + [limit])


# --------------------------------------------------------------------------- offers & placements
class OfferRepository:
    def insert_offer(self, cur, data):
        return insert_row(cur, "offers", data)

    def get_offer(self, cur, offer_id):
        return fetch_one(cur, "SELECT * FROM offers WHERE offer_id = %s", (offer_id,))

    def by_application(self, cur, application_id):
        return fetch_one(cur, "SELECT * FROM offers WHERE application_id = %s", (application_id,))

    def update_offer(self, cur, offer_id, data):
        return update_row(cur, "offers", "offer_id", offer_id, data)

    def next_id(self, cur):
        return next_id(cur, "offers", "offer_id")

    def insert_placement(self, cur, data):
        return insert_row(cur, "placements", data)

    def update_placement(self, cur, placement_id, data):
        return update_row(cur, "placements", "placement_id", placement_id, data)

    def placement_by_offer(self, cur, offer_id):
        return fetch_one(cur, "SELECT * FROM placements WHERE offer_id = %s", (offer_id,))

    def search_offers(self, cur, filters: dict, limit: int = 100):
        where, params = _where({
            "offer_status": ("o.offer_status", "eq"),
            "candidate_id": ("a.candidate_id", "eq"),
        }, filters)
        return fetch_all(cur, f"""SELECT o.offer_id, o.offer_code, o.application_id, c.candidate_code,
                                         c.full_name AS candidate, j.job_code, co.company_name, o.designation,
                                         o.offered_package_lpa, o.offer_date, o.expected_joining_date, o.offer_status
                                  FROM offers o
                                  JOIN applications a ON a.application_id = o.application_id
                                  JOIN candidates c ON c.candidate_id = a.candidate_id
                                  JOIN jobs j ON j.job_id = a.job_id
                                  JOIN companies co ON co.company_id = j.company_id
                                  WHERE {where} ORDER BY o.offer_id LIMIT %s""", params + [limit])

    def search_placements(self, cur, filters: dict, limit: int = 100):
        where, params = _where({
            "joining_status": ("p.joining_status", "eq"),
            "candidate_id": ("p.candidate_id", "eq"),
            "company_id": ("p.company_id", "eq"),
        }, filters)
        return fetch_all(cur, f"""SELECT p.placement_id, c.candidate_code, c.full_name AS candidate,
                                         co.company_name, j.job_code, p.designation, p.final_package_lpa,
                                         p.expected_joining_date, p.actual_joining_date, p.joining_status,
                                         p.placement_status
                                  FROM placements p
                                  JOIN candidates c ON c.candidate_id = p.candidate_id
                                  JOIN companies co ON co.company_id = p.company_id
                                  JOIN jobs j ON j.job_id = p.job_id
                                  WHERE {where} ORDER BY p.placement_id LIMIT %s""", params + [limit])
