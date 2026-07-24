from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app import db
from app.forms import ProfileForm
from app.utils import save_avatar

profile_bp = Blueprint("profile", __name__, template_folder="../templates/profile")


@profile_bp.route("/")
@login_required
def view():
    return render_template("profile/view.html", user=current_user)


@profile_bp.route("/edit", methods=["GET", "POST"])
@login_required
def edit():
    form = ProfileForm(obj=current_user)
    profile = current_user.profile

    if not form.is_submitted():
        form.phone.data = profile.phone
        form.address.data = profile.address
        form.linkedin.data = profile.linkedin
        form.github.data = profile.github
        form.portfolio.data = profile.portfolio

    if form.validate_on_submit():
        current_user.full_name = form.full_name.data

        profile.phone = form.phone.data
        profile.address = form.address.data
        profile.linkedin = form.linkedin.data
        profile.github = form.github.data
        profile.portfolio = form.portfolio.data

        if form.profile_picture.data:
            saved_path = save_avatar(form.profile_picture.data)
            if saved_path:
                profile.profile_picture = saved_path
            else:
                flash("Profile picture must be a PNG or JPG file — nothing else was saved either, please retry.", "danger")
                return render_template("profile/edit.html", form=form)

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("profile.view"))

    elif form.is_submitted():
        # validate_on_submit() failed — surface exactly why instead of silently
        # re-rendering with no explanation (this previously looked identical
        # to "my save didn't work" with zero clue as to the real cause).
        for field_name, errors in form.errors.items():
            label = getattr(form, field_name).label.text if hasattr(form, field_name) else field_name
            for err in errors:
                flash(f"{label}: {err}", "danger")
        if not form.errors:
            flash("Your session expired before saving — please try again.", "danger")

    return render_template("profile/edit.html", form=form)
