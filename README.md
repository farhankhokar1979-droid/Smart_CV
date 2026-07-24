# SmartCV — AI-Powered Resume Builder & ATS Optimization System

A fully offline-first Flask application for building, importing, scoring, and exporting
professional resumes — built in 10 phases, each tested end-to-end.

## Tech Stack

- **Backend:** Python 3, Flask, SQLAlchemy, Flask-Login, Flask-WTF, Flask-Migrate
- **Database:** SQLite
- **Frontend:** HTML5, CSS3 (custom design system, no framework), vanilla JS
- **Import/OCR:** PyMuPDF, python-docx, Tesseract OCR, Pillow
- **Export:** WeasyPrint (PDF), python-docx (DOCX)
- **AI:** Groq API (llama-3.1-8b-instant, free tier) with rule-based offline fallback for every feature

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# System dependency for OCR (Ubuntu/Debian):
sudo apt-get install tesseract-ocr
# Windows: winget install --id UB-Mannheim.TesseractOCR
# then set pytesseract.pytesseract.tesseract_cmd in app/importers.py

# System dependency for PDF export (Windows only — Linux/Mac usually fine out of the box):
# Install the GTK3 runtime: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer

# Initialize the database + seed a default admin and starter templates:
python3 init_db.py

# Run:
python3 run.py
```

App runs at `http://127.0.0.1:5000`.

**Default admin login:** `admin@smartcv.io` / `Admin@12345` — change this password
immediately in a real deployment (Profile → Change Password).

### Optional: enable real AI generation (Groq)

By default, every AI feature (summary writer, improver) runs on rule-based
offline heuristics — no setup required. To use a real LLM instead:

1. Get a free API key at https://console.groq.com/keys
2. Copy `.env.example` to `.env` and paste your key:
   ```
   GROQ_API_KEY=your_key_here
   ```
3. Restart the app.

`app/ai_engine.py` checks for a configured key on every AI call and only
falls back to heuristics if it's missing or the request fails — so this
requires no code changes, just the `.env` file.

Note: this makes those two specific features require internet (Groq is a
hosted API, not local) — everything else in SmartCV stays fully offline.
ATS scoring, keyword matching, duplicate detection, and template
recommendation are rule-based by design either way and never call any API.

## Project Structure

```
smartcv/
├── app/
│   ├── models/          # User, UserProfile, Resume, Template, ResumeSection,
│   │                     SectionEntry, ResumeHistory, ActivityLog
│   ├── routes/          # auth, main, profile, resumes, dashboard, admin blueprints
│   ├── templates/        # one subfolder per area, each with its own CSS file
│   ├── static/css/       # base.css (design system) + one file per template folder
│   ├── section_types.py # field schema for all 12 resume section types + custom sections
│   ├── ai_engine.py      # Groq client + offline heuristic fallback
│   ├── importers.py      # PDF/DOCX/OCR text extraction + section splitting
│   ├── exporters.py      # PDF (WeasyPrint) / DOCX (python-docx) export
│   ├── resume_renderer.py # Jinja context builder + template rendering
│   └── utils.py          # file upload helpers, activity logging
├── config.py
├── run.py
├── init_db.py            # creates tables + seeds admin + starter templates
├── .env.example           # copy to .env to configure GROQ_API_KEY, SECRET_KEY
```

## Feature Summary by Phase

1. **Foundation** — auth (register/login/logout/forgot & change password), role-based
   access, base layout (sidebar + topbar), full design system ported from your
   MediMart CSS structure in a violet/teal palette.
2. **Profile & Resume Management** — profile editing (drag-and-drop picture upload,
   contact, social links), resume CRUD, auto-save, version history with restore.
3. **Resume Builder** — 12 built-in section types plus unlimited user-defined
   Custom Sections, add/edit/delete/hide/reorder at both the section and entry
   level, drag-and-drop.
4. **Templates** — 7 categories seeded, admin can write custom HTML/Jinja
   templates, per-resume color/font/layout customization, live preview.
   All templates support the user's uploaded profile picture and fill a full
   A4-height page regardless of content length.
5. **Import & OCR** — PDF/DOCX upload, automatic OCR fallback for scanned resumes,
   contact-info extraction, auto-populated builder sections.
6. **Export** — PDF (styled, via WeasyPrint) and DOCX (plain/ATS-safe, via
   python-docx).
7. **AI Modules** — Resume Writer, Improver, ATS Analyzer, Job Matcher. Real AI
   via Groq's free tier with automatic offline heuristic fallback. Recommended
   skills are one-click-to-add buttons on the AI Assistant page.
8. **Offline AI Logic Engine** — completeness engine, keyword engine, quality
   engine, duplicate checker, skill recommender, template recommender (these
   overlap with Phase 7 in the original spec, so they're implemented together
   in `ai_engine.py` rather than duplicated).
9. **Dashboards & Admin** — user/admin dashboards, admin Reports (usage stats,
   template popularity) and paginated System Logs backed by an ActivityLog model.
10. **Polish** — responsive layout, environment-configurable debug mode,
    `.gitignore`, this README.

## Notes & Honest Limitations

- **AI features run on heuristics by default** in any environment without a
  `GROQ_API_KEY` configured — this was tested and verified throughout.
- **DOCX export is intentionally plain** (not template-styled) to stay maximally
  ATS-parseable — this is standard resume-export practice.
- **Admin-authored templates use `render_template_string`** on trusted (admin-only)
  input — don't expose template creation to non-admin users without adding
  sandboxing.
- **Contact info and social links** (phone, address, LinkedIn, GitHub, portfolio)
  live on the user's Profile, not per-resume — they're shared across every
  resume you create. Edit them at Profile → Edit Profile.
