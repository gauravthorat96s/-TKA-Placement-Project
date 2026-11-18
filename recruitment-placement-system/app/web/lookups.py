"""Read-only lists used to fill dropdowns."""


def _all(db, sql):
    with db.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def candidates(db):
    return _all(db, "SELECT candidate_id, candidate_code, full_name FROM candidates ORDER BY candidate_code")


def open_jobs(db):
    return _all(db, "SELECT job_id, job_code, job_title FROM jobs WHERE status = 'OPEN' ORDER BY job_code")


def active_companies(db):
    return _all(db, "SELECT company_id, company_name FROM companies WHERE status = 'ACTIVE' ORDER BY company_name")


def skills(db):
    return _all(db, "SELECT skill_id, skill_name FROM skills WHERE is_active = 1 ORDER BY skill_name")
