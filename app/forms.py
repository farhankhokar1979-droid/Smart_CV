from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, URL


class RegisterForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match")],
    )
    submit = SubmitField("Create Account")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember Me")
    submit = SubmitField("Log In")


class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Send Reset Instructions")


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New Password", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match")],
    )
    submit = SubmitField("Reset Password")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current Password", validators=[DataRequired()])
    new_password = PasswordField("New Password", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[DataRequired(), EqualTo("new_password", message="Passwords must match")],
    )
    submit = SubmitField("Change Password")


class ProfileForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(min=2, max=120)])
    profile_picture = FileField(
        "Profile Picture", validators=[Optional(), FileAllowed(["png", "jpg", "jpeg"], "Images only.")]
    )
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    address = StringField("Address", validators=[Optional(), Length(max=255)])
    linkedin = StringField("LinkedIn URL", validators=[Optional(), URL(), Length(max=255)])
    github = StringField("GitHub URL", validators=[Optional(), URL(), Length(max=255)])
    portfolio = StringField("Portfolio URL", validators=[Optional(), URL(), Length(max=255)])
    submit = SubmitField("Save Changes")


class ResumeCreateForm(FlaskForm):
    title = StringField("Resume Title", validators=[DataRequired(), Length(min=1, max=150)])
    job_title = StringField("Target Job Title", validators=[Optional(), Length(max=150)])
    submit = SubmitField("Create Resume")


class ResumeRenameForm(FlaskForm):
    title = StringField("Resume Title", validators=[DataRequired(), Length(min=1, max=150)])
    submit = SubmitField("Rename")


class ResumeImportForm(FlaskForm):
    title = StringField("Resume Title", validators=[DataRequired(), Length(min=1, max=150)])
    resume_file = FileField(
        "Resume File (PDF or DOCX)",
        validators=[DataRequired(), FileAllowed(["pdf", "docx"], "PDF or DOCX only.")],
    )
    submit = SubmitField("Import Resume")
