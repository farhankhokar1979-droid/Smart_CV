"""One-off script to create tables, a default admin, and starter templates for local dev/testing."""
from app import create_app, db
from app.models.user import User, UserProfile
from app.models.resume import Template

DEFAULT_SOURCE = """<div style="font-family: '{{ style.font }}', sans-serif; padding: 40px; max-width: 800px; min-height: 1123px; box-sizing: border-box; margin: 0 auto; background: #fff;">
  {% if resume.owner and resume.owner.profile and resume.owner.profile.profile_picture %}
  <img src="{{ url_for('static', filename=resume.owner.profile.profile_picture) }}" style="width:90px; height:90px; border-radius:50%; object-fit:cover; margin-bottom:12px;">
  {% endif %}
  <h1 style="color: {{ style.primary_color }}; margin-bottom: 4px;">{{ resume.owner.full_name if resume.owner else "Your Name" }}</h1>
  {% if resume.job_title %}<p style="color:#666; margin-top:0;">{{ resume.job_title }}</p>{% endif %}
  <hr style="border: none; border-top: 2px solid {{ style.primary_color }};">
  {% for section in sections %}
    <h3 style="color: {{ style.primary_color }}; text-transform: uppercase; font-size: 13px; letter-spacing: .05em;">{{ section.label }}</h3>
    {% for entry in section.entries %}
      <div style="margin-bottom: 10px; font-size: 13.5px;">
        {% for k, v in entry.items() %}{% if v %}<div>{{ v }}</div>{% endif %}{% endfor %}
      </div>
    {% endfor %}
  {% endfor %}
</div>"""

STARTER_TEMPLATES = [
    ("ATS Clean", "ATS Friendly", "Plain single-column layout tuned for parsing.", "#0d9488"),
    ("Professional", "Professional", "Classic layout for corporate roles.", "#6d28d9"),
    ("Minimal", "Minimal", "Lots of whitespace, understated typography.", "#374151"),
    ("Modern Split", "Modern", "Two-column layout with a bold header.", "#ec4899"),
    ("Graduate", "Student", "Highlights education and projects for new grads.", "#0891b2"),
    ("Executive", "Executive", "Formal layout for senior leadership resumes.", "#4c1d95"),
    ("Creative Edge", "Creative", "Colorful accents for design/creative roles.", "#d97706"),
]

app = create_app()

with app.app_context():
    db.create_all()

    if not User.query.filter_by(email="admin@smartcv.io").first():
        admin = User(full_name="SmartCV Admin", email="admin@smartcv.io", role="admin")
        admin.set_password("Admin@12345")
        db.session.add(admin)
        db.session.flush()
        db.session.add(UserProfile(user_id=admin.id))
        db.session.commit()
        print("Created default admin: admin@smartcv.io / Admin@12345")
    else:
        print("Admin already exists.")

    if Template.query.count() == 0:
        for name, category, desc, color in STARTER_TEMPLATES:
            db.session.add(Template(
                name=name, category=category, description=desc,
                html_content=DEFAULT_SOURCE, thumbnail_color=color, is_enabled=True,
            ))
        db.session.commit()
        print(f"Seeded {len(STARTER_TEMPLATES)} starter templates.")
    else:
        print("Templates already seeded.")

    print("Database initialized.")
