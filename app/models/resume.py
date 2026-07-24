from datetime import datetime
import json
from app import db


class Resume(db.Model):
    __tablename__ = "resumes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey("templates.id"), nullable=True)

    title = db.Column(db.String(150), nullable=False, default="Untitled Resume")
    job_title = db.Column(db.String(150))

    is_default = db.Column(db.Boolean, default=False)
    ats_score = db.Column(db.Float, default=0.0)
    resume_score = db.Column(db.Float, default=0.0)

    style_settings = db.Column(db.Text, default="{}")  # JSON: colors, font, header_style, layout, margins, line_spacing, columns
    target_job_description = db.Column(db.Text)  # pasted JD used by the AI Job Matcher / ATS Analyzer

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    template = db.relationship("Template")

    def get_style(self):
        defaults = {
            "primary_color": "#6d28d9",
            "font": "Inter",
            "header_style": "centered",
            "layout": "single-column",
            "margin": "normal",
            "line_spacing": "normal",
        }
        try:
            saved = json.loads(self.style_settings) if self.style_settings else {}
        except (ValueError, TypeError):
            saved = {}
        defaults.update(saved)
        return defaults

    def set_style(self, d):
        self.style_settings = json.dumps(d)

    def __repr__(self):
        return f"<Resume {self.title} (user={self.user_id})>"


class Template(db.Model):
    __tablename__ = "templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))  # ATS Friendly, Professional, Minimal, Modern, Student, Executive, Creative
    description = db.Column(db.String(255))

    # A small Jinja2 snippet rendered with {resume, sections_data, style} in context (see resume_renderer.py).
    html_content = db.Column(db.Text)

    thumbnail_color = db.Column(db.String(20), default="#6d28d9")
    thumbnail_image = db.Column(db.String(255))  # optional admin-uploaded preview image, relative static path
    is_enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Template {self.name}>"


class ResumeHistory(db.Model):
    """Lightweight snapshot log for Resume auto-save / history / restore."""
    __tablename__ = "resume_history"

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id"), nullable=False)

    title = db.Column(db.String(150))
    job_title = db.Column(db.String(150))
    snapshot_data = db.Column(db.Text)  # JSON blob; expands in Phase 3 to hold section data

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    resume = db.relationship("Resume", backref=db.backref("history", lazy="dynamic", cascade="all, delete-orphan"))

    def __repr__(self):
        return f"<ResumeHistory resume_id={self.resume_id} at={self.created_at}>"


class ResumeSection(db.Model):
    """One section (Summary, Education, Experience, Skills, ...) within a resume.
    Section-level ordering + hide/show is stored here; the actual repeatable
    items (e.g. each job in Experience) live in SectionEntry."""
    __tablename__ = "resume_sections"

    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id"), nullable=False)

    section_type = db.Column(db.String(30), nullable=False)  # matches SECTION_TYPES key in section_types.py
    custom_label = db.Column(db.String(100))  # user-given title, only used when section_type == "custom"
    order_index = db.Column(db.Integer, default=0)
    is_hidden = db.Column(db.Boolean, default=False)
    column = db.Column(db.String(10), default="main")  # "main" or "sidebar" — which side a 2-column template places this in

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    resume = db.relationship("Resume", backref=db.backref("sections", lazy="dynamic", cascade="all, delete-orphan"))

    def __repr__(self):
        return f"<ResumeSection {self.section_type} (resume={self.resume_id})>"


class SectionEntry(db.Model):
    """A single repeatable item within a section — one job in Experience,
    one degree in Education, one skill in Skills, etc."""
    __tablename__ = "section_entries"

    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey("resume_sections.id"), nullable=False)

    data = db.Column(db.Text, nullable=False, default="{}")  # JSON dict of field_name -> value
    order_index = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    section = db.relationship("ResumeSection", backref=db.backref("entries", lazy="dynamic", cascade="all, delete-orphan"))

    def get_data(self):
        try:
            return json.loads(self.data) if self.data else {}
        except (ValueError, TypeError):
            return {}

    def set_data(self, d):
        self.data = json.dumps(d)

    def __repr__(self):
        return f"<SectionEntry section={self.section_id}>"
