"""Field schema for each resume builder section type.

Each entry: label, whether the section allows only one entry (e.g. Summary)
or many (e.g. Experience), and the ordered list of (field_name, label, input_type)
tuples used to render add/edit forms and display entries generically.
"""

SECTION_TYPES = {
    "summary": {
        "label": "Summary",
        "icon": "fa-solid fa-align-left",
        "single_entry": True,
        "fields": [("text", "Professional Summary", "textarea")],
    },
    "objective": {
        "label": "Career Objective",
        "icon": "fa-solid fa-bullseye",
        "single_entry": True,
        "fields": [("text", "Career Objective", "textarea")],
    },
    "education": {
        "label": "Education",
        "icon": "fa-solid fa-graduation-cap",
        "single_entry": False,
        "fields": [
            ("institution", "Institution", "text"),
            ("degree", "Degree / Program", "text"),
            ("start_date", "Start Date", "text"),
            ("end_date", "End Date", "text"),
            ("description", "Description", "textarea"),
        ],
    },
    "experience": {
        "label": "Experience",
        "icon": "fa-solid fa-briefcase",
        "single_entry": False,
        "fields": [
            ("company", "Company", "text"),
            ("position", "Position", "text"),
            ("start_date", "Start Date", "text"),
            ("end_date", "End Date", "text"),
            ("description", "Description", "textarea"),
        ],
    },
    "skills": {
        "label": "Skills",
        "icon": "fa-solid fa-gears",
        "single_entry": False,
        "fields": [
            ("name", "Skill", "text"),
            ("level", "Proficiency (e.g. Advanced)", "text"),
        ],
    },
    "projects": {
        "label": "Projects",
        "icon": "fa-solid fa-diagram-project",
        "single_entry": False,
        "fields": [
            ("name", "Project Name", "text"),
            ("tech_stack", "Tech Stack", "text"),
            ("link", "Link", "text"),
            ("description", "Description", "textarea"),
        ],
    },
    "certifications": {
        "label": "Certifications",
        "icon": "fa-solid fa-certificate",
        "single_entry": False,
        "fields": [
            ("name", "Certification Name", "text"),
            ("issuer", "Issuing Organization", "text"),
            ("date", "Date", "text"),
        ],
    },
    "languages": {
        "label": "Languages",
        "icon": "fa-solid fa-language",
        "single_entry": False,
        "fields": [
            ("name", "Language", "text"),
            ("proficiency", "Proficiency", "text"),
        ],
    },
    "achievements": {
        "label": "Achievements",
        "icon": "fa-solid fa-trophy",
        "single_entry": False,
        "fields": [
            ("title", "Achievement", "text"),
            ("description", "Description", "textarea"),
        ],
    },
    "internships": {
        "label": "Internships",
        "icon": "fa-solid fa-user-tie",
        "single_entry": False,
        "fields": [
            ("company", "Company", "text"),
            ("role", "Role", "text"),
            ("start_date", "Start Date", "text"),
            ("end_date", "End Date", "text"),
            ("description", "Description", "textarea"),
        ],
    },
    "volunteer_work": {
        "label": "Volunteer Work",
        "icon": "fa-solid fa-hand-holding-heart",
        "single_entry": False,
        "fields": [
            ("organization", "Organization", "text"),
            ("role", "Role", "text"),
            ("description", "Description", "textarea"),
        ],
    },
    "references": {
        "label": "References",
        "icon": "fa-solid fa-address-book",
        "single_entry": False,
        "fields": [
            ("name", "Name", "text"),
            ("relationship", "Relationship", "text"),
            ("contact", "Contact Info", "text"),
        ],
    },
    "custom": {
        "label": "Custom Section",
        "icon": "fa-solid fa-star",
        "single_entry": False,
        "is_custom": True,
        "fields": [
            ("title", "Item Title", "text"),
            ("content", "Details", "textarea"),
        ],
    },
}

SECTION_ORDER_DEFAULT = list(SECTION_TYPES.keys())
