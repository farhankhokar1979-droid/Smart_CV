from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models.resume import Resume

dashboard_bp = Blueprint("dashboard", __name__, template_folder="../templates/dashboard")


@dashboard_bp.route("/")
@login_required
def index():
    resume_count = current_user.resumes.count()
    recent_resumes = current_user.resumes.order_by(Resume.updated_at.desc()).limit(5).all()
    return render_template(
        "dashboard/user_dashboard.html",
        resume_count=resume_count,
        recent_resumes=recent_resumes,
    )
