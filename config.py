import os
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(basedir, "instance", "smartcv.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload settings
    UPLOAD_FOLDER = os.path.join(basedir, "app", "static", "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    ALLOWED_RESUME_EXTENSIONS = {"pdf", "docx"}
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}

    # WTF
    WTF_CSRF_ENABLED = True

    # AI — Groq (free tier). Leave unset to run purely on offline heuristic fallback.
    # Easiest option: paste your key directly as the default string below (between the quotes).
    # (Or, if you prefer, set GROQ_API_KEY as an environment variable / in a .env file instead —
    # either way works, this line just checks the environment first, then falls back to what's here.)
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")