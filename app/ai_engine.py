"""Offline-first AI engine for SmartCV.

Every function here tries the Groq API first (free tier, llama-3.1-8b-instant
by default — fast, hosted inference, requires a GROQ_API_KEY and internet).
If no API key is configured, the request fails, or Groq is unreachable, each
function falls back to a rule-based heuristic so the feature still works
end-to-end with zero setup and zero internet.

To enable real AI generation: set GROQ_API_KEY in your .env file (get a free
key at https://console.groq.com/keys) — no code changes needed, _call_groq()
picks it up automatically via config.py.
"""
import re
import requests
from flask import current_app

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_TIMEOUT = 10

WEAK_OPENERS = {
    "responsible for": "Led",
    "worked on": "Delivered",
    "helped with": "Contributed to",
    "involved in": "Drove",
    "was tasked with": "Owned",
    "duties included": "Delivered",
}

# Small offline skill-recommendation database, keyed by role keyword.
SKILL_DB = {
    # Tech
    "software engineer": ["Python", "Git", "SQL", "Docker", "REST API", "Flask"],
    "backend developer": ["Python", "Flask", "PostgreSQL", "Docker", "REST API", "Git"],
    "frontend developer": ["JavaScript", "React", "HTML/CSS", "TypeScript", "Git"],
    "full stack developer": ["JavaScript", "Python", "React", "SQL", "Git", "REST API"],
    "mobile developer": ["Swift", "Kotlin", "React Native", "Flutter", "Git"],
    "devops engineer": ["Docker", "Kubernetes", "CI/CD", "AWS", "Linux", "Terraform"],
    "data analyst": ["SQL", "Excel", "Python", "Power BI", "Statistics"],
    "data scientist": ["Python", "Pandas", "Machine Learning", "SQL", "Statistics"],
    "business analyst": ["SQL", "Excel", "Requirements Gathering", "Data Visualization", "Stakeholder Management"],
    "network engineer": ["Networking", "Cisco", "TCP/IP", "Firewalls", "VPN"],
    "cybersecurity analyst": ["Network Security", "SIEM", "Risk Assessment", "Penetration Testing", "Incident Response"],
    "designer": ["Figma", "UI/UX", "Adobe XD", "Prototyping", "Wireframing"],
    "product manager": ["Roadmapping", "Agile", "Stakeholder Management", "User Research", "Analytics"],
    "project manager": ["Agile", "Scrum", "Jira", "Stakeholder Management", "Risk Management"],
    "qa engineer": ["Test Automation", "Selenium", "Manual Testing", "Bug Tracking", "SQL"],

    # Healthcare
    "physician": ["Patient Care", "Diagnosis", "Clinical Documentation", "Treatment Planning", "Medical Ethics"],
    "doctor": ["Patient Care", "Diagnosis", "Clinical Documentation", "Treatment Planning", "Medical Ethics"],
    "nurse": ["Patient Care", "Vital Signs Monitoring", "Medication Administration", "Clinical Documentation", "Triage"],
    "pharmacist": ["Medication Dispensing", "Drug Interactions", "Patient Counseling", "Inventory Management", "Regulatory Compliance"],
    "dentist": ["Patient Care", "Oral Diagnosis", "Dental Procedures", "Treatment Planning", "Sterilization Protocols"],
    "veterinarian": ["Animal Care", "Diagnosis", "Surgery", "Client Communication", "Preventive Medicine"],
    "physiotherapist": ["Patient Assessment", "Treatment Planning", "Rehabilitation Techniques", "Manual Therapy", "Patient Education"],

    # Education
    "teacher": ["Lesson Planning", "Classroom Management", "Curriculum Development", "Student Assessment", "Communication"],
    "professor": ["Curriculum Development", "Research", "Public Speaking", "Academic Writing", "Mentoring"],

    # Business & Finance
    "accountant": ["Bookkeeping", "Tax Preparation", "Financial Reporting", "Excel", "Reconciliation"],
    "financial analyst": ["Financial Modeling", "Excel", "Forecasting", "Valuation", "Data Analysis"],
    "auditor": ["Risk Assessment", "Compliance", "Financial Reporting", "Internal Controls", "Attention to Detail"],
    "lawyer": ["Legal Research", "Contract Drafting", "Negotiation", "Case Management", "Litigation"],
    "hr": ["Recruitment", "Employee Relations", "Onboarding", "Performance Management", "HRIS"],
    "human resources": ["Recruitment", "Employee Relations", "Onboarding", "Performance Management", "HRIS"],

    # Sales, Marketing, Ops
    "sales representative": ["CRM", "Negotiation", "Lead Generation", "Cold Calling", "Relationship Building"],
    "marketing": ["Social Media Marketing", "SEO", "Content Strategy", "Google Analytics", "Campaign Management"],
    "customer service": ["Communication", "Problem Solving", "CRM Software", "Conflict Resolution", "Multitasking"],
    "administrative assistant": ["Scheduling", "Microsoft Office", "Data Entry", "Communication", "Organization"],
    "chef": ["Menu Planning", "Food Safety", "Kitchen Management", "Inventory Control", "Plating"],

    # Engineering (non-software)
    "mechanical engineer": ["CAD", "SolidWorks", "Product Design", "GD&T", "Manufacturing Processes"],
    "civil engineer": ["AutoCAD", "Structural Analysis", "Project Management", "Site Inspection", "Building Codes"],
    "electrician": ["Electrical Wiring", "Circuit Design", "Troubleshooting", "Safety Codes", "Blueprint Reading"],
}

# Universal, role-agnostic fallback — shown only when the job title matches
# nothing above, instead of nonsensically defaulting to tech skills.
GENERIC_FALLBACK_SKILLS = ["Communication", "Problem Solving", "Time Management", "Teamwork", "Adaptability"]

STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "to", "of", "in", "on", "with", "is",
    "are", "as", "at", "by", "be", "this", "that", "we", "you", "our", "will",
    "have", "has", "from", "your", "their", "it", "job", "role", "team",
}


def _call_groq(prompt):
    """Returns generated text from the Groq API, or None if unavailable/unconfigured."""
    try:
        api_key = current_app.config.get("GROQ_API_KEY")
        model = current_app.config.get("GROQ_MODEL", "llama-3.1-8b-instant")
    except RuntimeError:
        return None  # no app context (e.g. called outside a request)

    if not api_key:
        return None  # no key configured — go straight to fallback, no wasted request

    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 300,
            },
            timeout=GROQ_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip() or None
    except (requests.RequestException, KeyError, IndexError, ValueError):
        pass
    return None


def entries_text(sections, types):
    """Flatten entry values from the given section types into a list of strings."""
    out = []
    for section in sections:
        if section["type"] in types:
            for entry in section["entries"]:
                out.extend(v for v in entry.values() if v)
    return out


# ── AI Resume Writer ─────────────────────────────────────────────────

def generate_summary(resume_title_job, sections):
    skills = entries_text(sections, ["skills"])[:5]
    experience = entries_text(sections, ["experience"])[:2]

    prompt = (
        f"Write a concise, professional 2-sentence resume summary for a "
        f"{resume_title_job or 'professional'}. Skills: {', '.join(skills) or 'various'}. "
        f"Experience highlights: {' | '.join(experience) or 'entry-level'}. "
        f"Return only the summary text, no preamble."
    )
    ai_text = _call_groq(prompt)
    if ai_text:
        return ai_text

    # Offline fallback: templated sentence.
    role = resume_title_job or "professional"
    skill_str = ", ".join(skills) if skills else "a range of relevant skills"
    return (
        f"Motivated {role} with hands-on experience and strong skills in {skill_str}. "
        f"Proven ability to deliver results and collaborate effectively across teams."
    )


# ── AI Resume Improver ───────────────────────────────────────────────

def improve_text(text):
    if not text or not text.strip():
        return text

    prompt = (
        f"Rewrite this resume bullet point to be more professional, action-oriented, "
        f"and concise. Return only the rewritten text:\n\n{text}"
    )
    ai_text = _call_groq(prompt)
    if ai_text:
        return ai_text

    # Offline fallback: weak-opener replacement + cleanup.
    result = text.strip()
    for weak, strong in WEAK_OPENERS.items():
        pattern = re.compile(re.escape(weak), re.IGNORECASE)
        result = pattern.sub(strong, result, count=1)
    result = re.sub(r"\s{2,}", " ", result)
    if result and result[0].islower():
        result = result[0].upper() + result[1:]
    return result


# ── AI ATS Analyzer / Job Matcher ────────────────────────────────────

def _tokenize(text):
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#./-]{1,}", (text or "").lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 2]


def ats_analysis(sections, job_description=None):
    all_text = " ".join(
        v for section in sections for entry in section["entries"] for v in entry.values() if v
    )
    resume_tokens = set(_tokenize(all_text))

    present_types = {s["type"] for s in sections}
    required = ["summary", "experience", "education", "skills"]
    missing_sections = [r for r in required if r not in present_types]

    result = {
        "missing_sections": missing_sections,
        "completeness_pct": round(100 * (len(required) - len(missing_sections)) / len(required)),
        "matched_keywords": [],
        "missing_keywords": [],
        "keyword_score": None,
        "weak_bullets": [],
        "long_sentences": [],
    }

    # Weak bullets & long sentences (Experience Analyzer / Quality Engine)
    for section in sections:
        for entry in section["entries"]:
            for v in entry.values():
                if not v:
                    continue
                lowered = v.lower()
                if any(lowered.startswith(w) for w in WEAK_OPENERS):
                    result["weak_bullets"].append(v[:80])
                word_count = len(v.split())
                if word_count > 28:
                    result["long_sentences"].append(v[:80])

    if job_description and job_description.strip():
        jd_tokens = set(_tokenize(job_description))
        matched = jd_tokens & resume_tokens
        missing = jd_tokens - resume_tokens
        result["matched_keywords"] = sorted(matched)[:20]
        result["missing_keywords"] = sorted(missing)[:20]
        result["keyword_score"] = round(100 * len(matched) / len(jd_tokens)) if jd_tokens else 0

    # Overall ATS score: blend completeness + keyword match (if available) + bullet quality
    quality_penalty = min(20, len(result["weak_bullets"]) * 3 + len(result["long_sentences"]) * 2)
    base = result["completeness_pct"]
    if result["keyword_score"] is not None:
        base = round((result["completeness_pct"] + result["keyword_score"]) / 2)
    result["ats_score"] = max(0, min(100, base - quality_penalty))

    return result


def recommend_skills(job_title):
    if not job_title:
        return []
    lowered = job_title.lower().strip()

    # Match the longest/most specific role phrase first — e.g. "backend developer"
    # should win over a shorter, looser match before falling through.
    matches = [role for role in SKILL_DB if role in lowered]
    if matches:
        best = max(matches, key=len)
        return SKILL_DB[best]

    # No confident match — return universal soft skills instead of guessing
    # (previously this silently defaulted to tech skills for *any* unmatched
    # role, which is wrong for e.g. "Physician").
    return GENERIC_FALLBACK_SKILLS


# ── Duplicate Checker ─────────────────────────────────────────────────

def find_duplicates(sections):
    """Flag repeated skill names and near-identical bullet lines across the resume."""
    seen_skills = {}
    duplicate_skills = []
    seen_bullets = {}
    duplicate_bullets = []

    for section in sections:
        for entry in section["entries"]:
            if section["type"] in ("skills", "languages", "certifications"):
                name = (entry.get("name") or "").strip().lower()
                if name:
                    if name in seen_skills:
                        duplicate_skills.append(entry.get("name"))
                    seen_skills[name] = True
            else:
                text = (entry.get("description") or entry.get("text") or "").strip().lower()
                if text and len(text) > 15:
                    key = re.sub(r"\s+", " ", text)[:60]
                    if key in seen_bullets:
                        duplicate_bullets.append(text[:80])
                    seen_bullets[key] = True

    return {"duplicate_skills": duplicate_skills, "duplicate_bullets": duplicate_bullets}


# ── Template Recommendation Engine ────────────────────────────────────

def recommend_template_category(job_title, sections):
    """Suggest a template category based on job role and experience signals."""
    lowered = (job_title or "").lower()
    experience_count = sum(len(s["entries"]) for s in sections if s["type"] == "experience")

    if any(w in lowered for w in ["student", "intern", "graduate", "entry"]):
        return "Student"
    if any(w in lowered for w in ["director", "vp", "chief", "head of", "executive", "president"]):
        return "Executive"
    if any(w in lowered for w in ["designer", "creative", "artist", "illustrator"]):
        return "Creative"
    if experience_count == 0:
        return "Student"
    if experience_count >= 4:
        return "Executive"
    return "Professional"
