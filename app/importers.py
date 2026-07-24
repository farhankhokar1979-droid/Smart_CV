"""Resume import pipeline: PDF/DOCX text extraction (with OCR fallback for
scanned PDFs), contact-info extraction, and heuristic section splitting.

Fully offline: PyMuPDF for PDF text + rasterization, Tesseract for OCR,
python-docx for Word files, plain regex for contact/section detection.
No network calls anywhere in this module.
"""
import re
import io

import fitz  # PyMuPDF
import docx
import pytesseract
from PIL import Image
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}")
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9_-]+", re.I)
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_-]+", re.I)

# Section header keywords -> our internal section_type. Checked line-by-line,
# case-insensitively, against short lines (likely headers, not body text).
SECTION_HEADER_KEYWORDS = [
    (["summary", "professional summary"], "summary"),
    (["objective", "career objective"], "objective"),
    (["education", "academic background"], "education"),
    (["experience", "work experience", "employment history", "professional experience"], "experience"),
    (["skills", "technical skills", "core competencies"], "skills"),
    (["projects", "personal projects", "academic projects"], "projects"),
    (["certifications", "certificates", "licenses"], "certifications"),
    (["languages"], "languages"),
    (["achievements", "awards", "honors"], "achievements"),
    (["internships", "internship experience"], "internships"),
    (["volunteer", "volunteer work", "community service"], "volunteer_work"),
    (["references"], "references"),
]


def extract_pdf_text(filepath):
    """Return (text, used_ocr). Tries the PDF's text layer first; falls back
    to rasterizing pages and running Tesseract OCR if little/no text is found."""
    doc = fitz.open(filepath)
    text_parts = [page.get_text() for page in doc]
    text = "\n".join(text_parts).strip()

    if len(text) > 40:  # looks like a real text layer
        doc.close()
        return text, False

    # Likely a scanned resume — OCR each page.
    ocr_parts = []
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        ocr_parts.append(pytesseract.image_to_string(img))
    doc.close()
    return "\n".join(ocr_parts).strip(), True


def extract_docx_text(filepath):
    document = docx.Document(filepath)
    return "\n".join(p.text for p in document.paragraphs if p.text.strip())


def extract_contact_info(text):
    email_match = EMAIL_RE.search(text)
    phone_match = PHONE_RE.search(text)
    linkedin_match = LINKEDIN_RE.search(text)
    github_match = GITHUB_RE.search(text)
    return {
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0) if phone_match else None,
        "linkedin": linkedin_match.group(0) if linkedin_match else None,
        "github": github_match.group(0) if github_match else None,
    }


def split_into_sections(text):
    """Heuristically split raw resume text into {section_type: raw_block}
    using short lines that match known section header keywords."""
    lines = [ln.strip() for ln in text.splitlines()]

    header_positions = []  # (line_index, section_type)
    for i, line in enumerate(lines):
        if not line or len(line) > 40:
            continue
        lowered = line.lower().strip(":").strip()
        for keywords, section_type in SECTION_HEADER_KEYWORDS:
            if lowered in keywords:
                header_positions.append((i, section_type))
                break

    sections = {}
    intro_end = header_positions[0][0] if header_positions else min(len(lines), 8)
    intro_text = "\n".join(lines[:intro_end]).strip()
    if intro_text:
        sections["summary"] = intro_text

    for idx, (line_no, section_type) in enumerate(header_positions):
        end = header_positions[idx + 1][0] if idx + 1 < len(header_positions) else len(lines)
        block = "\n".join(lines[line_no + 1:end]).strip()
        if block:
            sections[section_type] = block

    return sections
