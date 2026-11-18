"""URL routes. Each page maps to one of the 12 prototype pages."""
import functools

from flask import (Blueprint, Response, current_app, flash, redirect, render_template, request,
                   session, url_for)

from app.exceptions import RPMSError
from app.models.entities import User
from app.web import lookups
from app.web.helpers import parse_skills, rows_to_csv, skills_to_text

bp = Blueprint("rpms", __name__)
CANDIDATE_FILTERS = ("candidate_code", "full_name", "mobile", "email", "primary_technology",
                     "passing_year", "qualification", "placement_status")
TECHNOLOGIES = ["Java", "Python", "Testing", "Data Analytics"]
QUALIFICATIONS = ["BE", "BTech", "MCA", "BCA", "BSc Computer Science", "MSc Computer Science"]
QUAL_RULES = ["BE", "BTech", "MCA", "BCA", "BSc", "Any Graduate"]
APPLICATION_STATUSES = ["APPLIED", "ELIGIBILITY_VERIFIED", "SHORTLISTED", "INTERVIEW_SCHEDULED", "INTERVIEWED",
                        "SELECTED", "OFFERED", "JOINED", "REJECTED", "WITHDRAWN"]


def svc():
    return current_app.extensions["rpms"]


def actor() -> User:
    u = session["user"]
    return User(user_id=u["user_id"], username=u["username"], full_name=u["full_name"], role_code=u["role_code"])


def login_required(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("rpms.login"))
        return view(*args, **kwargs)
    return wrapper


def guarded(view):
    """Action routes: a business-rule error becomes a flash message, then back to the page."""
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except RPMSError as exc:
            message = str(exc)
            reasons = getattr(exc, "reasons", [])
            if reasons:
                message += " " + "; ".join(reasons)
            flash(message, "error")
            return redirect(request.referrer or url_for("rpms.dashboard"))
    return wrapper


def ok(message):
    flash(message, "success")
    return redirect(request.referrer or url_for("rpms.dashboard"))


# ------------------------------------------------------------------ login
@bp.route("/")
def index():
    return redirect(url_for("rpms.dashboard") if "user" in session else url_for("rpms.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        try:
            user = svc().auth.login(request.form.get("username"), request.form.get("password"))
        except RPMSError as exc:
            flash(str(exc), "error")
        else:
            session.clear()
            session["user"] = {"user_id": user.user_id, "username": user.username,
                               "full_name": user.full_name, "role_code": user.role_code}
            return redirect(url_for("rpms.dashboard"))
    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("rpms.login"))


# ------------------------------------------------------------------ dashboard
@bp.route("/dashboard")
@login_required
def dashboard():
    s = svc()
    return render_template(
        "dashboard.html",
        summary=s.reports.dashboard(),
        funnel=s.reports.run("recruitment_funnel")[0],
        pending=s.reports.run("pending_interviews"),
        open_jobs=s.jobs.search({"status": "OPEN"})[:5],
        placements=s.placements.list_placements({})[:5],
    )


# ------------------------------------------------------------------ candidates
@bp.route("/candidates")
@login_required
def candidates():
    filters = {k: request.args.get(k, "") for k in CANDIDATE_FILTERS}
    return render_template("candidates.html", rows=svc().candidates.search(filters, 100), filters=filters,
                           technologies=TECHNOLOGIES, qualifications=QUALIFICATIONS)


@bp.route("/candidates/new", methods=["GET", "POST"])
@login_required
def candidate_new():
    s = svc()
    if request.method == "POST":
        form = request.form.to_dict()
        try:
            code = s.candidates.register(actor(), form, skills=parse_skills(request.form.get("skills"), "proficiency_level"))
        except RPMSError as exc:
            flash(str(exc), "error")
            return render_template("candidate_form.html", candidate=form, skills_text=request.form.get("skills", ""),
                                   edit_id=None, technologies=TECHNOLOGIES, qualifications=QUALIFICATIONS)
        flash(f"Candidate {code} registered.", "success")
        return redirect(url_for("rpms.candidates"))
    return render_template("candidate_form.html", candidate=None, skills_text="", edit_id=None,
                           technologies=TECHNOLOGIES, qualifications=QUALIFICATIONS)


@bp.route("/candidates/<int:candidate_id>")
@login_required
@guarded
def candidate_detail(candidate_id):
    return render_template("candidate_details.html", p=svc().candidates.profile(candidate_id))


@bp.route("/candidates/<int:candidate_id>/edit", methods=["GET", "POST"])
@login_required
def candidate_edit(candidate_id):
    s = svc()
    if request.method == "POST":
        form = request.form.to_dict()
        skills_text = request.form.get("skills", "")
        try:
            s.candidates.update(actor(), candidate_id, form,
                                skills=parse_skills(skills_text, "proficiency_level") if skills_text.strip() else None)
        except RPMSError as exc:
            flash(str(exc), "error")
            return render_template("candidate_form.html", candidate=form, skills_text=skills_text, edit_id=candidate_id,
                                   technologies=TECHNOLOGIES, qualifications=QUALIFICATIONS)
        flash("Candidate updated.", "success")
        return redirect(url_for("rpms.candidate_detail", candidate_id=candidate_id))
    try:
        profile = s.candidates.profile(candidate_id)
    except RPMSError as exc:
        flash(str(exc), "error")
        return redirect(url_for("rpms.candidates"))
    return render_template("candidate_form.html", candidate=profile["candidate"],
                           skills_text=skills_to_text(profile["skills"], "proficiency_level", True), edit_id=candidate_id,
                           technologies=TECHNOLOGIES, qualifications=QUALIFICATIONS)


@bp.route("/candidates/<int:candidate_id>/deactivate", methods=["POST"])
@login_required
@guarded
def candidate_deactivate(candidate_id):
    svc().candidates.deactivate(actor(), candidate_id)
    return ok("Candidate set to INACTIVE.")


# ------------------------------------------------------------------ companies
@bp.route("/companies", methods=["GET", "POST"])
@login_required
def companies():
    s = svc()
    if request.method == "POST":
        try:
            code = s.companies.create(actor(), request.form.to_dict())
        except RPMSError as exc:
            flash(str(exc), "error")
        else:
            flash(f"Company {code} added.", "success")
        return redirect(url_for("rpms.companies"))
    filters = {"company_name": request.args.get("company_name", ""), "status": request.args.get("status", "")}
    return render_template("companies.html", rows=s.companies.search(filters), filters=filters)


@bp.route("/companies/<int:company_id>/deactivate", methods=["POST"])
@login_required
@guarded
def company_deactivate(company_id):
    svc().companies.deactivate(actor(), company_id)
    return ok("Company set to INACTIVE.")


# ------------------------------------------------------------------ jobs
@bp.route("/jobs")
@login_required
def jobs():
    filters = {k: request.args.get(k, "") for k in ("job_code", "status", "technology", "company_id")}
    return render_template("jobs.html", rows=svc().jobs.search(filters), filters=filters,
                           statuses=["DRAFT", "OPEN", "CLOSED", "CANCELLED"])


@bp.route("/jobs/<int:job_id>/status", methods=["POST"])
@login_required
@guarded
def job_status(job_id):
    svc().jobs.set_status(actor(), job_id, request.form.get("status"))
    return ok("Job status updated.")


@bp.route("/jobs/new", methods=["GET", "POST"])
@bp.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
@login_required
def job_form(job_id=None):
    s = svc()
    companies_list = lookups.active_companies(s.db)
    skills_list = lookups.skills(s.db)
    if request.method == "POST":
        data = request.form.to_dict()
        data["qualifications"] = request.form.getlist("qualifications")
        skills_rows = parse_skills(request.form.get("skills"), "minimum_level")
        try:
            if job_id is None:
                code = s.jobs.create(actor(), data, skills=skills_rows)
                flash(f"Job {code} created.", "success")
            else:
                s.jobs.update(actor(), job_id, data, skills=skills_rows)
                flash("Job updated.", "success")
        except RPMSError as exc:
            flash(str(exc), "error")
            return render_template("job_form.html", job=data, job_id=job_id, skills_text=request.form.get("skills", ""),
                                   companies=companies_list, skills_list=skills_list, qual_rules=QUAL_RULES)
        return redirect(url_for("rpms.jobs"))
    job, skills_text = None, ""
    if job_id is not None:
        try:
            detail = s.jobs.detail(job_id)
        except RPMSError as exc:
            flash(str(exc), "error")
            return redirect(url_for("rpms.jobs"))
        job = detail["job"]
        skills_text = skills_to_text(detail["skills"], "minimum_level", False)
    return render_template("job_form.html", job=job, job_id=job_id, skills_text=skills_text,
                           companies=companies_list, skills_list=skills_list, qual_rules=QUAL_RULES)


# ------------------------------------------------------------------ applications
@bp.route("/applications")
@login_required
def applications():
    s = svc()
    filters = {k: request.args.get(k, "") for k in ("application_status", "candidate_id", "job_id", "date_from", "date_to")}
    history_id = request.args.get("history", type=int)
    history = s.applications.history(history_id) if history_id else None
    return render_template("applications.html", rows=s.applications.search(filters), filters=filters,
                           statuses=APPLICATION_STATUSES, candidates=lookups.candidates(s.db),
                           jobs=lookups.open_jobs(s.db), history=history, history_id=history_id)


@bp.route("/applications/apply", methods=["POST"])
@login_required
@guarded
def application_apply():
    code = svc().applications.apply(actor(), request.form.get("candidate_id", type=int),
                                    request.form.get("job_id", type=int), request.form.get("source") or "Portal")
    return ok(f"Application {code} submitted.")


@bp.route("/applications/<int:application_id>/eligibility", methods=["POST"])
@login_required
@guarded
def application_eligibility(application_id):
    result = svc().applications.check_eligibility(actor(), application_id)
    return ok(("Eligible: " if result.eligible else "Not eligible: ") + result.summary)


@bp.route("/applications/<int:application_id>/status", methods=["POST"])
@login_required
@guarded
def application_status(application_id):
    svc().applications.change_status(actor(), application_id, request.form.get("status"), request.form.get("remarks"))
    return ok("Application status updated.")


# ------------------------------------------------------------------ interviews
@bp.route("/interviews")
@login_required
def interviews():
    s = svc()
    filters = {k: request.args.get(k, "") for k in ("status", "date_from", "date_to")}
    apps = [a for a in s.applications.search({}) if a["application_status"] in ("SHORTLISTED", "INTERVIEWED")]
    return render_template("interviews.html", rows=s.interviews.search(filters), filters=filters, applications=apps)


@bp.route("/interviews/schedule", methods=["POST"])
@login_required
@guarded
def interview_schedule():
    f = request.form
    iv = svc().interviews.schedule(actor(), f.get("application_id", type=int), f.get("round_type"), f.get("interview_date"),
                                   f.get("interview_time"), f.get("mode") or "ONLINE", f.get("interviewer"), f.get("location"))
    return ok(f"Interview scheduled (ID {iv}).")


@bp.route("/interviews/<int:interview_id>/reschedule", methods=["POST"])
@login_required
@guarded
def interview_reschedule(interview_id):
    svc().interviews.reschedule(actor(), interview_id, request.form.get("interview_date"), request.form.get("interview_time"))
    return ok("Interview rescheduled.")


@bp.route("/interviews/<int:interview_id>/no-show", methods=["POST"])
@login_required
@guarded
def interview_no_show(interview_id):
    svc().interviews.mark_no_show(actor(), interview_id)
    return ok("Marked as no-show.")


@bp.route("/interviews/<int:interview_id>/feedback", methods=["POST"])
@login_required
@guarded
def interview_feedback(interview_id):
    f = request.form
    svc().interviews.submit_feedback(actor(), interview_id, f.get("recommendation"),
                                     {"overall_rating": f.get("overall_rating")}, f.get("remarks"))
    return ok("Feedback recorded.")


# ------------------------------------------------------------------ placement process
@bp.route("/placements")
@login_required
def placements():
    s = svc()
    selected = [a for a in s.applications.search({}) if a["application_status"] == "SELECTED"]
    return render_template("placement_process.html", offers=s.placements.list_offers({}),
                           placements=s.placements.list_placements({}), selected=selected)


@bp.route("/placements/offers", methods=["POST"])
@login_required
@guarded
def offer_create():
    f = request.form
    code = svc().placements.create_offer(actor(), f.get("application_id", type=int), f.get("designation"),
                                         f.get("package_lpa"), f.get("offer_date"), f.get("expected_joining_date"), f.get("remarks"))
    return ok(f"Offer {code} issued.")


@bp.route("/placements/offers/<int:offer_id>/status", methods=["POST"])
@login_required
@guarded
def offer_status(offer_id):
    svc().placements.update_offer_status(actor(), offer_id, request.form.get("status"), request.form.get("remarks"))
    return ok("Offer status updated.")


@bp.route("/placements/offers/<int:offer_id>/joining", methods=["POST"])
@login_required
@guarded
def offer_joining(offer_id):
    svc().placements.confirm_joining(actor(), offer_id, request.form.get("joining_status"), request.form.get("actual_joining_date"))
    return ok("Joining recorded.")


# ------------------------------------------------------------------ reports
@bp.route("/reports")
@login_required
def reports():
    s = svc()
    name = request.args.get("name") or s.reports.available()[0][0]
    filters = {"date_from": request.args.get("date_from", ""), "date_to": request.args.get("date_to", "")}
    return render_template("reports.html", available=s.reports.available(), name=name, filters=filters,
                           rows=s.reports.run(name, filters))


@bp.route("/reports/export")
@login_required
def reports_export():
    s = svc()
    name = request.args.get("name")
    rows = s.reports.run(name, {"date_from": request.args.get("date_from", ""), "date_to": request.args.get("date_to", "")})
    return Response(rows_to_csv(rows), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={name}.csv"})
