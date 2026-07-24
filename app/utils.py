import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app

from app import db
from app.models.activity import ActivityLog


def allowed_file(filename, allowed_extensions):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in allowed_extensions
    )


def save_image(file_storage, subfolder):
    """Save an uploaded image under static/uploads/<subfolder>/ and return its
    relative static path, or None if no file / invalid type."""
    if not file_storage or not file_storage.filename:
        return None

    if not allowed_file(file_storage.filename, current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
        return None

    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    filename = secure_filename(f"{uuid.uuid4().hex}.{ext}")

    upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], subfolder)
    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, filename)
    file_storage.save(filepath)

    return f"uploads/{subfolder}/{filename}"


def save_avatar(file_storage):
    """Save an uploaded profile picture and return its relative static path, or None."""
    return save_image(file_storage, "avatars")


def save_template_thumbnail(file_storage):
    """Save an admin-uploaded template preview image and return its relative static path, or None."""
    return save_image(file_storage, "template_thumbnails")


def log_activity(user, action, details=""):
    """Best-effort activity log write — never blocks the request if it fails."""
    try:
        entry = ActivityLog(
            user_id=user.id if user and getattr(user, "is_authenticated", True) else None,
            action=action,
            details=details[:255] if details else None,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
