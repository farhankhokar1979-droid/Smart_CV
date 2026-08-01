import os
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))


def _normalize_db_url(url):
    """Neon (and most managed Postgres providers) hand out URLs starting with
    'postgres://', but SQLAlchemy 1.4+/2.0 requires 'postgresql://' — this
    silently breaks the connection otherwise."""
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

    # Local dev falls back to SQLite; set DATABASE_URL (e.g. your Neon connection
    # string) as a Vercel environment variable in production.
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(
        os.environ.get("DATABASE_URL")
    ) or "sqlite:///" + os.path.join(basedir, "instance", "smartcv.db")

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,  # avoids "server closed the connection" on serverless cold starts
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload settings
    UPLOAD_FOLDER = os.path.join(basedir, "app", "static", "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    ALLOWED_RESUME_EXTENSIONS = {"pdf", "docx"}
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}

    WTF_CSRF_ENABLED = True

    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "PASTE_YOUR_GROQ_API_KEY_HERE")
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")