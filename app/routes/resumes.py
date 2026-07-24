import json
import io
import os
import uuid
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort, current_app, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app import db, csrf
from app.forms import ResumeCreateForm, ResumeRenameForm, ResumeImportForm
from app.models.resume import Resume, ResumeHistory, ResumeSection, SectionEntry, Template
from app.section_types import SECTION_TYPES
from app.resume_renderer import render_resume
from app.importers import extract_pdf_text, extract_docx_text, extract_contact_info, split_into_sections
from app.exporters import export_pdf, export_docx
from app.resume_renderer import build_render_context
from app import ai_engine
from app.utils import log_activity

resumes_bp = Blueprint("resumes", __name__, template_folder="../templates/resumes")

MAX_HISTORY_ENTRIES = 20


def _get_owned_resume_or_404(resume_id):
    resume = Resume.query.get_or_404(resume_id)
    if resume.user_id != current_user.id:
        abort(403)
    return resume


def _snapshot(resume):
    """Write a ResumeHistory row and trim old entries beyond MAX_HISTORY_ENTRIES."""
    entry = ResumeHistory(
        resume_id=resume.id,
        title=resume.title,
        job_title=resume.job_title,
        snapshot_data=json.dumps({"title": resume.title, "job_title": resume.job_title}),
    )
    db.session.add(entry)
    db.session.flush()

    old_entries = (
        ResumeHistory.query.filter_by(resume_id=resume.id)
        .order_by(ResumeHistory.created_at.desc())
        .offset(MAX_HISTORY_ENTRIES)
        .all()
    )
    for old in old_entries:
        db.session.delete(old)


@resumes_bp.route("/")
@login_required
def index():
    resumes = current_user.resumes.order_by(Resume.updated_at.desc()).all()
    return render_template("resumes/index.html", resumes=resumes)


@resumes_bp.route("/import", methods=["GET", "POST"])
@login_required
def import_resume():
    form = ResumeImportForm()

    if form.validate_on_submit():
        file_storage = form.resume_file.data
        ext = file_storage.filename.rsplit(".", 1)[1].lower()
        filename = secure_filename(f"{uuid.uuid4().hex}.{ext}")

        upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "resumes")
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)
        file_storage.save(filepath)

        used_ocr = False
        try:
            if ext == "pdf":
                text, used_ocr = extract_pdf_text(filepath)
            else:
                text = extract_docx_text(filepath)
        except Exception:
            flash("Could not read that file — please try a different PDF or DOCX.", "danger")
            return render_template("resumes/import.html", form=form)

        if not text or len(text.strip()) < 10:
            flash("No readable text was found in that file.", "warning")
            return render_template("resumes/import.html", form=form)

        contact = extract_contact_info(text)
        sections_text = split_into_sections(text)

        resume = Resume(user_id=current_user.id, title=form.title.data)
        db.session.add(resume)
        db.session.flush()

        # Save extracted contact info onto the profile if fields are still empty.
        profile = current_user.profile
        if contact.get("phone") and not profile.phone:
            profile.phone = contact["phone"]
        if contact.get("linkedin") and not profile.linkedin:
            profile.linkedin = contact["linkedin"]
        if contact.get("github") and not profile.github:
            profile.github = contact["github"]

        order = 0
        for section_type, raw_block in sections_text.items():
            if section_type not in SECTION_TYPES:
                continue
            meta = SECTION_TYPES[section_type]
            section = ResumeSection(resume_id=resume.id, section_type=section_type, order_index=order)
            db.session.add(section)
            db.session.flush()
            order += 1

            if meta["single_entry"]:
                entry = SectionEntry(section_id=section.id, order_index=0)
                entry.set_data({"text": raw_block})
                db.session.add(entry)
            elif any(f[0] == "description" for f in meta["fields"]):
                entry_data = {f[0]: "" for f in meta["fields"]}
                entry_data["description"] = raw_block
                entry = SectionEntry(section_id=section.id, order_index=0)
                entry.set_data(entry_data)
                db.session.add(entry)
            else:
                # List-style sections (skills, languages, certifications): one entry per line.
                first_field = meta["fields"][0][0]
                for i, line in enumerate([l.strip("-• \t") for l in raw_block.splitlines() if l.strip()][:25]):
                    entry_data = {f[0]: "" for f in meta["fields"]}
                    entry_data[first_field] = line
                    e = SectionEntry(section_id=section.id, order_index=i)
                    e.set_data(entry_data)
                    db.session.add(e)

        db.session.commit()

        log_activity(current_user, "resume_imported", f"{resume.title} ({ext.upper()})")
        msg = f"Imported {len(sections_text)} section(s) from your {ext.upper()} file."
        if used_ocr:
            msg += " (Scanned document — text recovered via OCR.)"
        flash(msg, "success")
        return redirect(url_for("resumes.edit", resume_id=resume.id))

    return render_template("resumes/import.html", form=form)


@resumes_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    form = ResumeCreateForm()
    if form.validate_on_submit():
        resume = Resume(
            user_id=current_user.id,
            title=form.title.data,
            job_title=form.job_title.data,
        )
        db.session.add(resume)
        db.session.commit()
        log_activity(current_user, "resume_created", resume.title)
        flash("Resume created.", "success")
        return redirect(url_for("resumes.edit", resume_id=resume.id))

    return render_template("resumes/create.html", form=form)


@resumes_bp.route("/<int:resume_id>/edit", methods=["GET"])
@login_required
def edit(resume_id):
    resume = _get_owned_resume_or_404(resume_id)
    sections = resume.sections.order_by(ResumeSection.order_index).all()

    sections_data = []
    for section in sections:
        meta = dict(SECTION_TYPES.get(section.section_type, {}))
        if section.section_type == "custom":
            meta["label"] = section.custom_label or "Custom Section"
        entries = section.entries.order_by(SectionEntry.order_index).all()
        sections_data.append({
            "section": section,
            "meta": meta,
            "entries": [{"obj": e, "data": e.get_data()} for e in entries],
        })

    existing_types = {s.section_type for s in sections}
    available_types = [
        (key, meta) for key, meta in SECTION_TYPES.items()
        if key not in existing_types or key == "custom"
    ]

    return render_template(
        "resumes/edit.html",
        resume=resume,
        sections_data=sections_data,
        available_types=available_types,
    )


@resumes_bp.route("/<int:resume_id>/sections/add", methods=["POST"])
@login_required
def add_section(resume_id):
    resume = _get_owned_resume_or_404(resume_id)
    section_type = request.form.get("section_type")
    custom_label = request.form.get("custom_label", "").strip()

    if section_type not in SECTION_TYPES:
        flash("Unknown section type.", "danger")
        return redirect(url_for("resumes.edit", resume_id=resume.id))

    if section_type == "custom" and not custom_label:
        flash("Please give your custom section a title.", "danger")
        return redirect(url_for("resumes.edit", resume_id=resume.id))

    if section_type != "custom":
        existing = resume.sections.filter_by(section_type=section_type).first()
        if existing:
            flash("That section has already been added.", "warning")
            return redirect(url_for("resumes.edit", resume_id=resume.id))

    max_order = db.session.query(db.func.max(ResumeSection.order_index)).filter_by(resume_id=resume.id).scalar() or 0
    default_column = "sidebar" if section_type in ("skills", "languages", "certifications") else "main"
    section = ResumeSection(
        resume_id=resume.id, section_type=section_type, order_index=max_order + 1,
        custom_label=custom_label if section_type == "custom" else None,
        column=default_column,
    )
    db.session.add(section)
    db.session.flush()

    if SECTION_TYPES[section_type]["single_entry"]:
        entry = SectionEntry(section_id=section.id, order_index=0)
        entry.set_data({})
        db.session.add(entry)

    db.session.commit()
    label = custom_label if section_type == "custom" else SECTION_TYPES[section_type]["label"]
    flash(f"'{label}' section added.", "success")
    return redirect(url_for("resumes.edit", resume_id=resume.id))


@resumes_bp.route("/<int:resume_id>/sections/<int:section_id>/toggle-hide", methods=["POST"])
@login_required
def toggle_section_hide(resume_id, section_id):
    resume = _get_owned_resume_or_404(resume_id)
    section = ResumeSection.query.get_or_404(section_id)
    if section.resume_id != resume.id:
        abort(403)
    section.is_hidden = not section.is_hidden
    db.session.commit()
    return redirect(url_for("resumes.edit", resume_id=resume.id))


@resumes_bp.route("/<int:resume_id>/sections/<int:section_id>/set-column", methods=["POST"])
@login_required
def set_section_column(resume_id, section_id):
    """Move a section between the main content area and the sidebar — only
    meaningful for two-column templates (single-column templates ignore this)."""
    resume = _get_owned_resume_or_404(resume_id)
    section = ResumeSection.query.get_or_404(section_id)
    if section.resume_id != resume.id:
        abort(403)
    section.column = "sidebar" if section.column != "sidebar" else "main"
    db.session.commit()
    return redirect(url_for("resumes.edit", resume_id=resume.id))


@resumes_bp.route("/<int:resume_id>/sections/<int:section_id>/delete", methods=["POST"])
@login_required
def delete_section(resume_id, section_id):
    resume = _get_owned_resume_or_404(resume_id)
    section = ResumeSection.query.get_or_404(section_id)
    if section.resume_id != resume.id:
        abort(403)
    db.session.delete(section)
    db.session.commit()
    flash("Section removed.", "info")
    return redirect(url_for("resumes.edit", resume_id=resume.id))


@resumes_bp.route("/<int:resume_id>/sections/reorder", methods=["POST"])
@login_required
@csrf.exempt
def reorder_sections(resume_id):
    resume = _get_owned_resume_or_404(resume_id)
    data = request.get_json(silent=True) or {}
    ordered_ids = data.get("section_ids", [])

    sections_by_id = {s.id: s for s in resume.sections.all()}
    for index, sid in enumerate(ordered_ids):
        section = sections_by_id.get(int(sid))
        if section:
            section.order_index = index
    db.session.commit()
    return jsonify({"status": "ok"})


@resumes_bp.route("/<int:resume_id>/sections/<int:section_id>/entries/add", methods=["POST"])
@login_required
def add_entry(resume_id, section_id):
    resume = _get_owned_resume_or_404(resume_id)
    section = ResumeSection.query.get_or_404(section_id)
    if section.resume_id != resume.id:
        abort(403)

    meta = SECTION_TYPES.get(section.section_type, {"fields": []})
    entry_data = {field_name: request.form.get(field_name, "") for field_name, _, _ in meta["fields"]}

    max_order = db.session.query(db.func.max(SectionEntry.order_index)).filter_by(section_id=section.id).scalar() or 0
    entry = SectionEntry(section_id=section.id, order_index=max_order + 1)
    entry.set_data(entry_data)
    db.session.add(entry)
    db.session.commit()
    flash("Entry added.", "success")
    return redirect(url_for("resumes.edit", resume_id=resume.id))


@resumes_bp.route("/<int:resume_id>/sections/<int:section_id>/entries/<int:entry_id>/update", methods=["POST"])
@login_required
def update_entry(resume_id, section_id, entry_id):
    resume = _get_owned_resume_or_404(resume_id)
    section = ResumeSection.query.get_or_404(section_id)
    entry = SectionEntry.query.get_or_404(entry_id)
    if section.resume_id != resume.id or entry.section_id != section.id:
        abort(403)

    meta = SECTION_TYPES.get(section.section_type, {"fields": []})
    entry_data = {field_name: request.form.get(field_name, "") for field_name, _, _ in meta["fields"]}
    entry.set_data(entry_data)
    db.session.commit()
    flash("Entry updated.", "success")
    return redirect(url_for("resumes.edit", resume_id=resume.id))


@resumes_bp.route("/<int:resume_id>/sections/<int:section_id>/entries/<int:entry_id>/delete", methods=["POST"])
@login_required
def delete_entry(resume_id, section_id, entry_id):
    resume = _get_owned_resume_or_404(resume_id)
    section = ResumeSection.query.get_or_404(section_id)
    entry = SectionEntry.query.get_or_404(entry_id)
    if section.resume_id != resume.id or entry.section_id != section.id:
        abort(403)
    db.session.delete(entry)
    db.session.commit()
    flash("Entry removed.", "info")
    return redirect(url_for("resumes.edit", resume_id=resume.id))


@resumes_bp.route("/<int:resume_id>/sections/<int:section_id>/entries/reorder", methods=["POST"])
@login_required
@csrf.exempt
def reorder_entries(resume_id, section_id):
    resume = _get_owned_resume_or_404(resume_id)
    section = ResumeSection.query.get_or_404(section_id)
    if section.resume_id != resume.id:
        abort(403)

    data = request.get_json(silent=True) or {}
    ordered_ids = data.get("entry_ids", [])

    entries_by_id = {e.id: e for e in section.entries.all()}
    for index, eid in enumerate(ordered_ids):
        entry = entries_by_id.get(int(eid))
        if entry:
            entry.order_index = index
    db.session.commit()
    return jsonify({"status": "ok"})


# ── PHASE 4: Templates & Customization ─────────────────────────────

@resumes_bp.route("/<int:resume_id>/template", methods=["GET", "POST"])
@login_required
def choose_template(resume_id):
    resume = _get_owned_resume_or_404(resume_id)

    if request.method == "POST":
        template_id = request.form.get("template_id", type=int)
        template = Template.query.filter_by(id=template_id, is_enabled=True).first()
        if template:
            resume.template_id = template.id
            db.session.commit()
            flash(f"Template '{template.name}' applied.", "success")
        else:
            flash("That template is not available.", "danger")
        return redirect(url_for("resumes.choose_template", resume_id=resume.id))

    templates = Template.query.filter_by(is_enabled=True).order_by(Template.category, Template.name).all()
    grouped = {}
    for t in templates:
        grouped.setdefault(t.category or "Other", []).append(t)

    context = build_render_context(resume)
    recommended_category = ai_engine.recommend_template_category(resume.job_title, context["sections"])

    return render_template(
        "resumes/templates.html", resume=resume, grouped=grouped,
        recommended_category=recommended_category,
    )


@resumes_bp.route("/<int:resume_id>/customize", methods=["GET", "POST"])
@login_required
def customize(resume_id):
    resume = _get_owned_resume_or_404(resume_id)
    style = resume.get_style()

    if request.method == "POST":
        style["primary_color"] = request.form.get("primary_color", style["primary_color"])
        style["font"] = request.form.get("font", style["font"])
        style["header_style"] = request.form.get("header_style", style["header_style"])
        style["layout"] = request.form.get("layout", style["layout"])
        style["margin"] = request.form.get("margin", style["margin"])
        style["line_spacing"] = request.form.get("line_spacing", style["line_spacing"])
        resume.set_style(style)
        db.session.commit()
        flash("Customization saved.", "success")
        return redirect(url_for("resumes.customize", resume_id=resume.id))

    return render_template("resumes/customize.html", resume=resume, style=style)


@resumes_bp.route("/<int:resume_id>/preview")
@login_required
def preview(resume_id):
    resume = _get_owned_resume_or_404(resume_id)
    rendered_html = render_resume(resume)
    return render_template("resumes/preview.html", resume=resume, rendered_html=rendered_html)


# ── PHASE 6: Export ─────────────────────────────────────────────────

def _safe_export_filename(resume, ext):
    base = "".join(c for c in resume.title if c.isalnum() or c in (" ", "-", "_")).strip() or "resume"
    return f"{base}.{ext}"


@resumes_bp.route("/<int:resume_id>/export/pdf")
@login_required
def export_pdf_route(resume_id):
    resume = _get_owned_resume_or_404(resume_id)
    pdf_bytes = export_pdf(resume)
    log_activity(current_user, "export_pdf", resume.title)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=_safe_export_filename(resume, "pdf"),
    )


@resumes_bp.route("/<int:resume_id>/export/docx")
@login_required
def export_docx_route(resume_id):
    resume = _get_owned_resume_or_404(resume_id)
    docx_bytes = export_docx(resume)
    log_activity(current_user, "export_docx", resume.title)
    return send_file(
        io.BytesIO(docx_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=_safe_export_filename(resume, "docx"),
    )


# ── PHASE 7: Offline AI Modules ──────────────────────────────────────

@resumes_bp.route("/<int:resume_id>/ai")
@login_required
def ai_dashboard(resume_id):
    resume = _get_owned_resume_or_404(resume_id)
    context = build_render_context(resume)
    sections = context["sections"]

    analysis = ai_engine.ats_analysis(sections, resume.target_job_description)
    duplicates = ai_engine.find_duplicates(sections)
    recommended_skills = ai_engine.recommend_skills(resume.job_title)
    current_skills = {v.lower() for v in ai_engine.entries_text(sections, ["skills"])}
    recommended_skills = [s for s in recommended_skills if s.lower() not in current_skills]

    # Keep the resume's stored scores in sync so the dashboard/list badges reflect the latest run.
    resume.ats_score = analysis["ats_score"]
    resume.resume_score = round((analysis["ats_score"] + analysis["completeness_pct"]) / 2)
    db.session.commit()

    # Build an entry list WITH ids (build_render_context strips them) so the
    # "Improve" button can target a specific entry.
    improvable_entries = []
    for db_section in resume.sections.order_by(ResumeSection.order_index).all():
        meta = SECTION_TYPES.get(db_section.section_type, {})
        for e in db_section.entries.order_by(SectionEntry.order_index).all():
            data = e.get_data()
            text_val = data.get("description") or data.get("text")
            if text_val:
                improvable_entries.append({
                    "section_id": db_section.id,
                    "entry_id": e.id,
                    "label": db_section.custom_label if db_section.section_type == "custom" and db_section.custom_label else meta.get("label", db_section.section_type.title()),
                    "text": text_val,
                })

    return render_template(
        "resumes/ai.html",
        resume=resume,
        analysis=analysis,
        duplicates=duplicates,
        recommended_skills=recommended_skills,
        improvable_entries=improvable_entries,
    )


@resumes_bp.route("/<int:resume_id>/ai/generate-summary", methods=["POST"])
@login_required
def ai_generate_summary(resume_id):
    resume = _get_owned_resume_or_404(resume_id)
    context = build_render_context(resume)

    summary_text = ai_engine.generate_summary(resume.job_title, context["sections"])

    section = resume.sections.filter_by(section_type="summary").first()
    if not section:
        max_order = db.session.query(db.func.max(ResumeSection.order_index)).filter_by(resume_id=resume.id).scalar() or 0
        section = ResumeSection(resume_id=resume.id, section_type="summary", order_index=max_order + 1)
        db.session.add(section)
        db.session.flush()

    entry = section.entries.first()
    if not entry:
        entry = SectionEntry(section_id=section.id, order_index=0)
        db.session.add(entry)
    entry.set_data({"text": summary_text})

    db.session.commit()
    flash("AI-generated summary added.", "success")
    return redirect(url_for("resumes.edit", resume_id=resume.id))


@resumes_bp.route("/<int:resume_id>/ai/improve-entry/<int:section_id>/<int:entry_id>", methods=["POST"])
@login_required
def ai_improve_entry(resume_id, section_id, entry_id):
    resume = _get_owned_resume_or_404(resume_id)
    section = ResumeSection.query.get_or_404(section_id)
    entry = SectionEntry.query.get_or_404(entry_id)
    if section.resume_id != resume.id or entry.section_id != section.id:
        abort(403)

    data = entry.get_data()
    field = "text" if "text" in data else ("description" if "description" in data else None)
    if field and data.get(field):
        data[field] = ai_engine.improve_text(data[field])
        entry.set_data(data)
        db.session.commit()
        flash("Entry improved by AI.", "success")
    else:
        flash("Nothing to improve in this entry.", "warning")

    return redirect(url_for("resumes.edit", resume_id=resume.id))


@resumes_bp.route("/<int:resume_id>/ai/job-match", methods=["POST"])
@login_required
def ai_job_match(resume_id):
    resume = _get_owned_resume_or_404(resume_id)
    resume.target_job_description = request.form.get("job_description", "").strip()
    db.session.commit()
    flash("Job description saved — analysis updated below.", "success")
    return redirect(url_for("resumes.ai_dashboard", resume_id=resume.id))


@resumes_bp.route("/<int:resume_id>/ai/add-skill", methods=["POST"])
@login_required
def ai_add_skill(resume_id):
    """One-click add for a recommended skill badge — creates the Skills
    section if needed, then adds the skill as a new entry."""
    resume = _get_owned_resume_or_404(resume_id)
    skill_name = request.form.get("skill_name", "").strip()
    if not skill_name:
        return redirect(url_for("resumes.ai_dashboard", resume_id=resume.id))

    section = resume.sections.filter_by(section_type="skills").first()
    if not section:
        max_order = db.session.query(db.func.max(ResumeSection.order_index)).filter_by(resume_id=resume.id).scalar() or 0
        section = ResumeSection(resume_id=resume.id, section_type="skills", order_index=max_order + 1)
        db.session.add(section)
        db.session.flush()

    already = any(
        (e.get_data().get("name") or "").lower() == skill_name.lower()
        for e in section.entries.all()
    )
    if not already:
        max_entry_order = db.session.query(db.func.max(SectionEntry.order_index)).filter_by(section_id=section.id).scalar() or 0
        entry = SectionEntry(section_id=section.id, order_index=max_entry_order + 1)
        entry.set_data({"name": skill_name, "level": ""})
        db.session.add(entry)
        db.session.commit()
        flash(f"Added '{skill_name}' to your Skills section.", "success")
    else:
        flash(f"'{skill_name}' is already in your Skills section.", "info")

    return redirect(url_for("resumes.ai_dashboard", resume_id=resume.id))


@resumes_bp.route("/<int:resume_id>/autosave", methods=["POST"])
@login_required
@csrf.exempt
def autosave(resume_id):
    resume = _get_owned_resume_or_404(resume_id)
    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    job_title = (data.get("job_title") or "").strip()

    if title:
        resume.title = title
    resume.job_title = job_title
    resume.updated_at = datetime.utcnow()

    _snapshot(resume)
    db.session.commit()

    return jsonify({"status": "ok", "saved_at": resume.updated_at.strftime("%I:%M:%S %p")})


@resumes_bp.route("/<int:resume_id>/rename", methods=["POST"])
@login_required
def rename(resume_id):
    resume = _get_owned_resume_or_404(resume_id)
    form = ResumeRenameForm()
    if form.validate_on_submit():
        resume.title = form.title.data
        db.session.commit()
        flash("Resume renamed.", "success")
    else:
        flash("Please provide a valid title.", "danger")
    return redirect(url_for("resumes.index"))


@resumes_bp.route("/<int:resume_id>/duplicate", methods=["POST"])
@login_required
def duplicate(resume_id):
    resume = _get_owned_resume_or_404(resume_id)
    copy = Resume(
        user_id=current_user.id,
        title=f"{resume.title} (Copy)",
        job_title=resume.job_title,
        template_id=resume.template_id,
        ats_score=resume.ats_score,
        resume_score=resume.resume_score,
    )
    db.session.add(copy)
    db.session.commit()
    flash("Resume duplicated.", "success")
    return redirect(url_for("resumes.index"))


@resumes_bp.route("/<int:resume_id>/delete", methods=["POST"])
@login_required
def delete(resume_id):
    resume = _get_owned_resume_or_404(resume_id)
    title = resume.title
    db.session.delete(resume)
    db.session.commit()
    log_activity(current_user, "resume_deleted", title)
    flash("Resume deleted.", "info")
    return redirect(url_for("resumes.index"))


@resumes_bp.route("/<int:resume_id>/history")
@login_required
def history(resume_id):
    resume = _get_owned_resume_or_404(resume_id)
    entries = resume.history.order_by(ResumeHistory.created_at.desc()).all()
    return render_template("resumes/history.html", resume=resume, entries=entries)


@resumes_bp.route("/<int:resume_id>/history/<int:history_id>/restore", methods=["POST"])
@login_required
def restore(resume_id, history_id):
    resume = _get_owned_resume_or_404(resume_id)
    entry = ResumeHistory.query.get_or_404(history_id)
    if entry.resume_id != resume.id:
        abort(403)

    resume.title = entry.title
    resume.job_title = entry.job_title
    db.session.commit()
    flash("Resume restored from history.", "success")
    return redirect(url_for("resumes.edit", resume_id=resume.id))
