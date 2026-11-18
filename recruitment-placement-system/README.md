# Recruitment & Placement Management System (RPMS)

A Python and MySQL application for managing candidates, companies, job requirements, applications, eligibility checks, interviews, offers, joining and placements in a training institute or placement office. It comes with a 12-page HTML/CSS UI prototype.

The project follows the three specification documents supplied with it: the Project Abstract, the UI Prototype Specification and the Database Design Specification. The traceability table in `docs/SPEC_TRACEABILITY.md` maps each requirement to the code that meets it.

## Project layout

```
recruitment-placement-system/
├── main.py                      Start the console application
├── requirements.txt             mysql-connector-python
├── app/
│   ├── config.py                Settings from environment variables
│   ├── exceptions.py            Error types (messages are safe to show users)
│   ├── models/                  Entities (dataclasses) and controlled status values
│   ├── db/
│   │   ├── connection.py        Connections and transactions (commit or roll back)
│   │   └── repositories.py      All SQL, parameterized, one class per area
│   ├── validation/validators.py Input rules and the exact validation messages
│   ├── services/                Business logic
│   │   ├── eligibility_engine.py  Candidate Eligibility Engine (pure rules)
│   │   ├── workflow.py          Allowed status transitions
│   │   ├── application_service.py, interview_service.py, placement_service.py
│   │   ├── candidate_service.py, master_service.py (companies and jobs)
│   │   ├── report_service.py    Runs the named reports
│   │   ├── authorization.py     Role permissions
│   │   └── auth_service.py      Login
│   ├── utils/                   Password hashing, logging, CSV import and export
│   └── cli/menus.py             Role-aware menus and prompts
├── database/
│   ├── database_schema.sql      17 tables, keys, constraints, indexes
│   ├── sample_data.sql          Demo data (30 candidates, 50 applications, ...)
│   └── reports.sql              Named management reports
├── scripts/
│   ├── init_database.py         Create the database and load sample data
│   └── demo_rollback.py         Shows that a failed transaction leaves no partial data
├── tests/                       Unit and end-to-end tests (standard library only)
├── docs/                        ER diagram, data changes, traceability
└── prototype-ui/                12 HTML pages + css/style.css + images/logo.png
```

## Requirements

- Python 3.10 or later
- MySQL 8.0 or later
- `pip install -r requirements.txt`

## Setup and run

1. **Create a database user** (recommended; do not use root in practice):

   ```sql
   CREATE USER 'rpms_app'@'localhost' IDENTIFIED BY 'choose-a-strong-password';
   GRANT ALL PRIVILEGES ON rpms_db.* TO 'rpms_app'@'localhost';
   GRANT CREATE, DROP ON *.* TO 'rpms_app'@'localhost';  -- needed once, to create the database
   ```

2. **Set connection settings** (defaults are shown):

   | Variable | Default |
   |---|---|
   | `RPMS_DB_HOST` | `localhost` |
   | `RPMS_DB_PORT` | `3306` |
   | `RPMS_DB_USER` | `rpms_app` |
   | `RPMS_DB_PASSWORD` | *(empty)* |
   | `RPMS_DB_NAME` | `rpms_db` |

3. **Install the driver and create the database:**

   ```bash
   pip install -r requirements.txt
   python scripts/init_database.py
   ```

   > `database_schema.sql` begins with `DROP DATABASE rpms_db`, which erases any existing data in that database. Run it on a fresh install or a test copy.

4. **Start the application:**

   ```bash
   python main.py
   ```

### Demo logins

Every demo account uses the password **`Demo@123`**. Change these before using the system for real.

| Username | Role | Can do |
|---|---|---|
| `admin` | Administrator | Everything |
| `amit.recruiter` | Recruiter | Candidates, jobs, applications, interviews, reports |
| `sneha.recruiter` | Recruiter | Same as above |
| `neha.placement` | Placement Officer | Candidates, companies, interviews, offers and placements, reports |
| `rahul.placement` | Placement Officer | Same as above |

## Web application (Flask)

Console सोबत एक browser-based interface सुद्धा आहे. दोन्ही एकाच services वापरतात, त्यामुळे validation, eligibility आणि transactions सारखेच चालतात.

```powershell
pip install -r requirements.txt
python run_web.py
```

Browser मध्ये `http://127.0.0.1:5000` उघडा आणि `admin` / `Demo@123` ने login करा.

Production साठी `RPMS_SECRET_KEY` environment variable सेट करा. Default value फक्त local testing साठी आहे.

Web tests: `python -m unittest tests.test_web`

## Running the tests

The tests do not need a MySQL server. They run the business rules directly, and they run the real service layer end to end against an SQLite stand-in, covering the full recruitment cycle, the rejections, the rollback and CSV import.

```bash
python -m unittest discover -s tests -t .
```

To confirm the transaction rollback against MySQL itself:

```bash
python scripts/demo_rollback.py
```

It should print `ROLLBACK VERIFIED`.

## Recruitment workflow

```
Register candidate -> Check eligibility -> Apply -> Verify eligibility -> Shortlist
  -> Schedule interview -> Record feedback -> (repeat rounds) -> Select
  -> Create offer -> Accept offer -> Confirm joining -> Placed
```

- **Eligibility** is checked before a candidate can apply. The engine checks job status and deadline, profile status, qualification, minimum percentage, passing-year window, backlog limit, experience, and mandatory skills with minimum proficiency. Every failed rule is reported, not just the first.
- **Status changes** follow the transition table in `app/services/workflow.py`. Statuses that come from interviews, offers and joining cannot be set by hand.
- **Transactions:** each multi-table step runs in one transaction. Joining confirmation, for example, inserts the placement, sets the candidate to PLACED, moves the application to JOINED and writes the audit trail. If any step fails, all of it is rolled back.
- **Audit:** every write adds a row to `activity_logs` and a line to `logs/rpms.log`. Application status changes also go to `application_history`.
- **Soft deletion:** candidates and companies are set INACTIVE rather than deleted, so history is kept.

## The UI prototype

The prototype is static HTML and CSS. It is not connected to the application. Open `prototype-ui/login.html` in a browser, or serve the folder with any static server. Links between pages work, and forms are not saved.

| Page | File |
|---|---|
| Login | `login.html` |
| Dashboard | `dashboard.html` |
| Candidate list | `candidates.html` |
| Candidate add/edit | `candidate-form.html` |
| Candidate details | `candidate-details.html` |
| Companies | `companies.html` |
| Job openings | `jobs.html` |
| Create/edit job | `job-form.html` |
| Applications | `applications.html` |
| Interviews | `interviews.html` |
| Placement process | `placement-process.html` |
| Reports | `reports.html` |

The stylesheet is `css/style.css`. It adapts to laptop, tablet and phone widths. The logo at `images/logo.png` is a placeholder. Replace it with the official Kiran Academy logo, keeping the same file name.

The prototype does not mention the backend language anywhere on its screens, as the specification requires.

## Design notes

- **Layers:** models, repositories (SQL), services (rules and transactions), and the console menus. Services receive a `Database` object, so the same code runs against MySQL in production and against SQLite in the tests.
- **Dependencies:** the MySQL driver is imported only when a connection is opened. The rules and the tests run without it.
- **Passwords:** PBKDF2-SHA256 with 200,000 iterations, from the Python standard library.
- **Reports:** the SQL lives in `database/reports.sql`, so you can read and change a report without touching Python. Filters are named parameters; `NULL` means "no filter".

## Known limitations

- Screenshots of the prototype pages are not included. Take them after you open the prototype in a browser.
- The console application is the only user interface. The HTML pages are a design prototype, as the specification intends.
- The Data Dictionary and MySQL Workbench export listed in the Database Design specification are not included. Generate them from the schema after you run it.
- Joining outcomes NOT_JOINED and NO_SHOW are final. A corrected outcome needs a new offer.
- There is no password reset or account management screen. The administrator creates accounts directly in the `users` table.
