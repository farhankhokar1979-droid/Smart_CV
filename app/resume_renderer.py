from flask import render_template_string
from app.models.resume import ResumeSection, SectionEntry
from app.section_types import SECTION_TYPES


def build_render_context(resume):
    """Assemble the {resume, sections, style} context used by every resume template."""
    sections = resume.sections.filter_by(is_hidden=False).order_by(ResumeSection.order_index).all()

    sections_data = []
    for section in sections:
        meta = SECTION_TYPES.get(section.section_type, {})
        entries = section.entries.order_by(SectionEntry.order_index).all()
        label = meta.get("label", section.section_type.title())
        if section.section_type == "custom" and section.custom_label:
            label = section.custom_label
        sections_data.append({
            "type": section.section_type,
            "label": label,
            "icon": meta.get("icon", "fa-solid fa-square"),
            "single_entry": meta.get("single_entry", False),
            "column": section.column or "main",
            "entries": [e.get_data() for e in entries],
        })

    return {
        "resume": resume,
        "sections": sections_data,
        "style": resume.get_style(),
    }


def render_resume(resume):
    """Render a Resume using its assigned Template's html_content (or a built-in fallback)."""
    context = build_render_context(resume)

    if resume.template and resume.template.html_content:
        return render_template_string(resume.template.html_content, **context)

    from flask import render_template
    return render_template("resumes/preview_fallback.html", **context)
