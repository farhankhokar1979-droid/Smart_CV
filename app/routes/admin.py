from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app import db
from app.models.user import User
from app.models.resume import Resume, Template
from app.models.activity import ActivityLog
from app.utils import log_activity, save_template_thumbnail

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")

TEMPLATE_CATEGORIES = [
    "ATS Friendly", "Professional", "Minimal", "Modern", "Student", "Executive", "Creative",
]

DEFAULT_TEMPLATE_SOURCE = """<div style="font-family: '{{ style.font }}', sans-serif; padding: 40px; max-width: 800px; min-height: 1123px; box-sizing: border-box; margin: 0 auto; background: #fff;">
  {% if resume.owner and resume.owner.profile and resume.owner.profile.profile_picture %}
  <img src="{{ url_for('static', filename=resume.owner.profile.profile_picture) }}" style="width:90px; height:90px; border-radius:50%; object-fit:cover; margin-bottom:12px;">
  {% endif %}
  <h1 style="color: {{ style.primary_color }}; margin-bottom: 4px;">{{ resume.owner.full_name if resume.owner else "Your Name" }}</h1>
  {% if resume.job_title %}<p style="color:#666; margin-top:0;">{{ resume.job_title }}</p>{% endif %}
  <hr style="border: none; border-top: 2px solid {{ style.primary_color }};">
  {% for section in sections %}
    <h3 style="color: {{ style.primary_color }}; text-transform: uppercase; font-size: 13px; letter-spacing: .05em;">{{ section.label }}</h3>
    {% for entry in section.entries %}
      <div style="margin-bottom: 10px; font-size: 13.5px;">
        {% for k, v in entry.items() %}{% if v %}<div>{{ v }}</div>{% endif %}{% endfor %}
      </div>
    {% endfor %}
  {% endfor %}
</div>"""


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/")
@login_required
@admin_required
def index():
    stats = {
        "user_count": User.query.count(),
        "resume_count": Resume.query.count(),
        "template_count": Template.query.count(),
    }
    return render_template("admin/dashboard.html", stats=stats)


@admin_bp.route("/templates")
@login_required
@admin_required
def templates_list():
    templates = Template.query.order_by(Template.category, Template.name).all()
    return render_template("admin/templates.html", templates=templates, categories=TEMPLATE_CATEGORIES)


@admin_bp.route("/templates/add", methods=["GET", "POST"])
@login_required
@admin_required
def templates_add():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "Professional")
        description = request.form.get("description", "").strip()
        html_content = request.form.get("html_content", "").strip() or DEFAULT_TEMPLATE_SOURCE
        color = request.form.get("thumbnail_color", "#6d28d9")

        if not name:
            flash("Template name is required.", "danger")
        else:
            t = Template(
                name=name, category=category, description=description,
                html_content=html_content, thumbnail_color=color, is_enabled=True,
            )
            thumb_file = request.files.get("thumbnail_image")
            if thumb_file and thumb_file.filename:
                saved_path = save_template_thumbnail(thumb_file)
                if saved_path:
                    t.thumbnail_image = saved_path
                else:
                    flash("Thumbnail image must be a PNG or JPG file — template saved without it.", "warning")
            db.session.add(t)
            db.session.commit()
            log_activity(current_user, "template_added", name)
            flash(f"Template '{name}' added.", "success")
            return redirect(url_for("admin.templates_list"))

    return render_template(
        "admin/template_form.html", template=None, categories=TEMPLATE_CATEGORIES,
        default_source=DEFAULT_TEMPLATE_SOURCE,
    )


@admin_bp.route("/templates/<int:template_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def templates_edit(template_id):
    t = Template.query.get_or_404(template_id)

    if request.method == "POST":
        t.name = request.form.get("name", t.name).strip()
        t.category = request.form.get("category", t.category)
        t.description = request.form.get("description", "").strip()
        t.html_content = request.form.get("html_content", t.html_content)
        t.thumbnail_color = request.form.get("thumbnail_color", t.thumbnail_color)

        thumb_file = request.files.get("thumbnail_image")
        if thumb_file and thumb_file.filename:
            saved_path = save_template_thumbnail(thumb_file)
            if saved_path:
                t.thumbnail_image = saved_path
            else:
                flash("Thumbnail image must be a PNG or JPG file — kept the previous one.", "warning")

        db.session.commit()
        log_activity(current_user, "template_edited", t.name)
        flash("Template updated.", "success")
        return redirect(url_for("admin.templates_list"))

    return render_template(
        "admin/template_form.html", template=t, categories=TEMPLATE_CATEGORIES,
        default_source=DEFAULT_TEMPLATE_SOURCE,
    )


@admin_bp.route("/templates/<int:template_id>/toggle", methods=["POST"])
@login_required
@admin_required
def templates_toggle(template_id):
    t = Template.query.get_or_404(template_id)
    t.is_enabled = not t.is_enabled
    db.session.commit()
    log_activity(current_user, "template_toggled", f"{t.name} -> {'enabled' if t.is_enabled else 'disabled'}")
    flash(f"Template {'enabled' if t.is_enabled else 'disabled'}.", "info")
    return redirect(url_for("admin.templates_list"))


@admin_bp.route("/templates/<int:template_id>/delete", methods=["POST"])
@login_required
@admin_required
def templates_delete(template_id):
    t = Template.query.get_or_404(template_id)
    name = t.name
    db.session.delete(t)
    db.session.commit()
    log_activity(current_user, "template_deleted", name)
    flash("Template deleted.", "info")
    return redirect(url_for("admin.templates_list"))


@admin_bp.route("/templates/<int:template_id>/preview")
@login_required
@admin_required
def templates_preview(template_id):
    t = Template.query.get_or_404(template_id)
    sample_resume = Resume.query.filter_by(user_id=current_user.id).first()

    if sample_resume:
        from app.resume_renderer import build_render_context
        from flask import render_template_string
        context = build_render_context(sample_resume)
        rendered = render_template_string(t.html_content, **context)
    else:
        rendered = "<p style='padding:40px; text-align:center; color:#999;'>Create a resume with some content first to preview real data here.</p>"

    return render_template("admin/template_preview.html", t=t, rendered_html=rendered)


@admin_bp.route("/reports")
@login_required
@admin_required
def reports():
    from sqlalchemy import func

    users_by_role = dict(db.session.query(User.role, func.count(User.id)).group_by(User.role).all())

    resumes_by_category = (
        db.session.query(Template.category, func.count(Resume.id))
        .join(Resume, Resume.template_id == Template.id)
        .group_by(Template.category)
        .all()
    )

    avg_ats = db.session.query(func.avg(Resume.ats_score)).scalar() or 0
    avg_resume_score = db.session.query(func.avg(Resume.resume_score)).scalar() or 0

    template_usage = (
        db.session.query(Template.name, func.count(Resume.id).label("uses"))
        .join(Resume, Resume.template_id == Template.id)
        .group_by(Template.name)
        .order_by(func.count(Resume.id).desc())
        .limit(10)
        .all()
    )

    action_counts = dict(
        db.session.query(ActivityLog.action, func.count(ActivityLog.id)).group_by(ActivityLog.action).all()
    )

    return render_template(
        "admin/reports.html",
        users_by_role=users_by_role,
        resumes_by_category=resumes_by_category,
        avg_ats=round(avg_ats, 1),
        avg_resume_score=round(avg_resume_score, 1),
        template_usage=template_usage,
        action_counts=action_counts,
        total_resumes=Resume.query.count(),
        total_users=User.query.count(),
    )


@admin_bp.route("/logs")
@login_required
@admin_required
def logs():
    page = request.args.get("page", 1, type=int)
    per_page = 30
    pagination = (
        ActivityLog.query.order_by(ActivityLog.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return render_template("admin/logs.html", pagination=pagination, entries=pagination.items)
