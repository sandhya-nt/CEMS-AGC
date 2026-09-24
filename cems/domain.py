"""Relational domain models for workflows not represented by the legacy app schema."""

from datetime import datetime, timedelta

from .extensions import db


VERIFICATION_TOKEN_EXPIRY_HOURS = 24
RESET_TOKEN_EXPIRY_HOURS = 2
TOKEN_BYTES = 32


class Role(db.Model):
    __tablename__ = "role"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class StudentProfile(db.Model):
    __tablename__ = "student_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), unique=True, nullable=False)
    student_id = db.Column(db.String(80), unique=True)
    roll_no = db.Column(db.String(50))
    course = db.Column(db.String(120))
    semester = db.Column(db.String(30))
    section = db.Column(db.String(20))
    academic_session = db.Column(db.String(20))
    batch = db.Column(db.String(20))
    department = db.Column(db.String(120))
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(20))
    profile_image = db.Column(db.String(255))
    bio = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("student_profile", uselist=False))


class OrganizerOnboardingEvent(db.Model):
    """Stores initial event information collected during organizer registration onboarding.
    This is separate from the main Event model and serves as draft/onboarding data."""
    __tablename__ = "organizer_onboarding_event"

    id = db.Column(db.Integer, primary_key=True)
    organizer_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    event_name = db.Column(db.String(180), nullable=False)
    event_category = db.Column(db.String(80))
    event_description = db.Column(db.Text)
    event_date = db.Column(db.Date)
    start_time = db.Column(db.String(20))
    end_time = db.Column(db.String(20))
    expected_participants = db.Column(db.Integer)
    venue = db.Column(db.String(160))
    venue_id = db.Column(db.Integer, db.ForeignKey("venue.id"), nullable=True)
    registration_deadline = db.Column(db.Date)
    event_fee = db.Column(db.Float, default=0)
    event_type = db.Column(db.String(30), default="free")
    event_poster = db.Column(db.String(255))
    additional_information = db.Column(db.Text)
    status = db.Column(db.String(30), default="draft")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organizer = db.relationship("User", backref=db.backref("onboarding_events", lazy="dynamic"))
    venue_ref = db.relationship("Venue", backref="onboarding_events")


class OrganizerProfile(db.Model):
    __tablename__ = "organizer_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), unique=True, nullable=False)
    employee_id = db.Column(db.String(80), unique=True)
    title = db.Column(db.String(120))
    department = db.Column(db.String(120))
    organizer_type = db.Column(db.String(80))
    designation = db.Column(db.String(120))
    contact_number = db.Column(db.String(30))
    official_email = db.Column(db.String(160))
    description = db.Column(db.Text)
    bio = db.Column(db.Text)
    profile_image = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("organizer_profile", uselist=False))


class AdminProfile(db.Model):
    __tablename__ = "admin_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), unique=True, nullable=False)
    employee_id = db.Column(db.String(80), unique=True)
    permissions_json = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("admin_profile", uselist=False))


class FacultyProfile(db.Model):
    __tablename__ = "faculty_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), unique=True, nullable=False)
    employee_id = db.Column(db.String(80), unique=True)
    department = db.Column(db.String(120))
    designation = db.Column(db.String(120))
    faculty_role = db.Column(db.String(80))
    academic_session = db.Column(db.String(20))
    bio = db.Column(db.Text)
    profile_image = db.Column(db.String(255))
    is_faculty_admin = db.Column(db.Boolean, default=False, nullable=False)
    admin_permissions_json = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("faculty_profile", uselist=False))

    # Faculty Admin permission constants
    PERMISSION_APPROVE_EVENTS = "approve_events"
    PERMISSION_MANAGE_USERS = "manage_users"
    PERMISSION_MANAGE_NOTICES = "manage_notices"
    PERMISSION_MONITOR_EVENTS = "monitor_events"
    PERMISSION_VIEW_REPORTS = "view_reports"
    PERMISSION_MANAGE_CERTIFICATES = "manage_certificates"
    PERMISSION_REVIEW_ACTIVITY = "review_activity"
    PERMISSION_ALL = [
        PERMISSION_APPROVE_EVENTS,
        PERMISSION_MANAGE_USERS,
        PERMISSION_MANAGE_NOTICES,
        PERMISSION_MONITOR_EVENTS,
        PERMISSION_VIEW_REPORTS,
        PERMISSION_MANAGE_CERTIFICATES,
        PERMISSION_REVIEW_ACTIVITY,
    ]

    def has_permission(self, permission: str) -> bool:
        """Check if faculty admin has a specific permission."""
        if not self.is_faculty_admin:
            return False
        perms = self.admin_permissions_json or []
        return permission in perms or "*" in perms

    def grant_permission(self, permission: str):
        """Grant a permission to this faculty admin."""
        if not self.is_faculty_admin:
            return
        perms = self.admin_permissions_json or []
        if permission not in perms:
            perms.append(permission)
            self.admin_permissions_json = perms

    def revoke_permission(self, permission: str):
        """Revoke a permission from this faculty admin."""
        perms = self.admin_permissions_json or []
        if permission in perms:
            perms.remove(permission)
            self.admin_permissions_json = perms

    def grant_all_permissions(self):
        """Grant all faculty admin permissions."""
        if self.is_faculty_admin:
            self.admin_permissions_json = ["*"]


class EventCategory(db.Model):
    __tablename__ = "event_category"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))
    color = db.Column(db.String(20), default="#6366f1")
    sort_order = db.Column(db.Integer, default=0)


class Ticket(db.Model):
    __tablename__ = "ticket"

    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey("registration.id", ondelete="CASCADE"), unique=True, nullable=False)
    qr_token = db.Column(db.String(120), unique=True, nullable=False)
    status = db.Column(db.String(30), default="active")
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    revoked_at = db.Column(db.DateTime)
    revoked_reason = db.Column(db.Text)

    registration = db.relationship("Registration", backref=db.backref("ticket_record", uselist=False))


class Payment(db.Model):
    __tablename__ = "payment"

    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey("registration.id", ondelete="CASCADE"), unique=True, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default="INR")
    provider = db.Column(db.String(40), nullable=False)
    provider_payment_id = db.Column(db.String(160), unique=True)
    transaction_id = db.Column(db.String(160), unique=True, nullable=False)
    payment_method = db.Column(db.String(40))
    status = db.Column(db.String(30), default="pending")
    raw_response_json = db.Column(db.JSON, default=dict)
    failure_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    paid_at = db.Column(db.DateTime)
    refunded_at = db.Column(db.DateTime)

    registration = db.relationship("Registration", backref=db.backref("payment_record", uselist=False))


class EventApprovalHistory(db.Model):
    __tablename__ = "event_approval_history"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    action = db.Column(db.String(50), nullable=False)
    from_status = db.Column(db.String(40))
    to_status = db.Column(db.String(40), nullable=False)
    comments = db.Column(db.Text)
    metadata_json = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    event = db.relationship("Event", backref="approval_history")
    actor = db.relationship("User", backref="approval_actions")


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    actor_role = db.Column(db.String(40))
    action = db.Column(db.String(80), nullable=False, index=True)
    entity_type = db.Column(db.String(80), nullable=False)
    entity_id = db.Column(db.Integer)
    description = db.Column(db.Text, nullable=False)
    metadata_json = db.Column(db.JSON, default=dict)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    actor = db.relationship("User", backref="audit_events")


class EventCustomField(db.Model):
    __tablename__ = "event_custom_field"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id", ondelete="CASCADE"), nullable=False, index=True)
    label = db.Column(db.String(180), nullable=False)
    field_type = db.Column(db.String(30), default="text")  # text, number, email, phone, dropdown, radio, checkbox, date, textarea, file
    required = db.Column(db.Boolean, default=False)
    options_json = db.Column(db.JSON, default=list)  # For dropdown, radio, checkbox options
    validation_json = db.Column(db.JSON, default=dict)  # Validation rules: min, max, pattern, min_length, max_length, etc.
    placeholder = db.Column(db.String(255))  # Placeholder text
    help_text = db.Column(db.String(500))  # Help text for the field
    position = db.Column(db.Integer, default=0)  # Display order
    is_active = db.Column(db.Boolean, default=True)  # Enable/disable field
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    event = db.relationship("Event", backref="custom_fields")

    # Field type constants
    FIELD_TYPES = [
        ("text", "Text (Single Line)"),
        ("textarea", "Text (Multi-line)"),
        ("number", "Number"),
        ("email", "Email"),
        ("phone", "Phone"),
        ("dropdown", "Dropdown (Select)"),
        ("radio", "Radio Buttons"),
        ("checkbox", "Checkboxes"),
        ("date", "Date"),
        ("file", "File Upload"),
    ]

    def get_options(self):
        """Get options as list of dicts with value and label."""
        opts = self.options_json or []
        if isinstance(opts, list):
            result = []
            for opt in opts:
                if isinstance(opt, dict):
                    result.append({"value": opt.get("value", ""), "label": opt.get("label", "")})
                elif isinstance(opt, str):
                    result.append({"value": opt, "label": opt})
            return result
        return []

    def set_options(self, options_list):
        """Set options from list of dicts or strings."""
        if isinstance(options_list, list):
            result = []
            for opt in options_list:
                if isinstance(opt, dict):
                    result.append({"value": opt.get("value", ""), "label": opt.get("label", "")})
                elif isinstance(opt, str):
                    result.append({"value": opt, "label": opt})
            self.options_json = result
        else:
            self.options_json = []

    def get_validation(self):
        """Get validation rules."""
        return self.validation_json or {}

    def set_validation(self, validation_dict):
        """Set validation rules."""
        if isinstance(validation_dict, dict):
            self.validation_json = validation_dict
        else:
            self.validation_json = {}


class EventCustomResponse(db.Model):
    __tablename__ = "event_custom_response"

    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey("registration.id", ondelete="CASCADE"), nullable=False, index=True)
    field_id = db.Column(db.Integer, db.ForeignKey("event_custom_field.id", ondelete="CASCADE"), nullable=False)
    value = db.Column(db.Text, nullable=False)  # For file uploads, stores the file path
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    registration = db.relationship("Registration", backref="custom_responses")
    field = db.relationship("EventCustomField")
    __table_args__ = (db.UniqueConstraint("registration_id", "field_id", name="uq_custom_response_registration_field"),)


class Reminder(db.Model):
    __tablename__ = "reminder"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    registration_id = db.Column(db.Integer, db.ForeignKey("registration.id", ondelete="CASCADE"))
    reminder_type = db.Column(db.String(30), nullable=False)
    scheduled_at = db.Column(db.DateTime, nullable=False, index=True)
    channel = db.Column(db.String(30), default="dashboard")
    status = db.Column(db.String(30), default="scheduled")
    sent_at = db.Column(db.DateTime)
    delivery_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    event = db.relationship("Event", backref="reminders")
    user = db.relationship("User", backref="event_reminders")
    registration = db.relationship("Registration", backref="reminders")


class EventActivity(db.Model):
    __tablename__ = "event_activity"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    action = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False)
    metadata_json = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    event = db.relationship("Event", backref="activity_log")
    actor = db.relationship("User", backref="event_activities")


class FeedbackFormTemplate(db.Model):
    """A customisable feedback form created by an organiser for one of their events.

    When an active template exists for an event, students fill out the *custom*
    form instead of (or in addition to) the static five-star feedback form.
    """
    __tablename__ = "feedback_form_template"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    questions = db.relationship("FeedbackFormQuestion", backref="template",
                                cascade="all, delete-orphan", order_by="FeedbackFormQuestion.position")
    responses = db.relationship("FeedbackFormResponse", back_populates="template",
                                cascade="all, delete-orphan")
    event = db.relationship("Event", backref="feedback_templates")
    creator = db.relationship("User", backref="feedback_form_templates")

    __table_args__ = (db.UniqueConstraint("event_id", name="uq_feedback_template_event"),)

    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "title": self.title,
            "description": self.description or "",
            "is_active": self.is_active,
            "question_count": len(self.questions),
            "response_count": len(self.responses),
        }


class FeedbackFormQuestion(db.Model):
    """An individual question inside a :class:`FeedbackFormTemplate`."""
    __tablename__ = "feedback_form_question"

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey("feedback_form_template.id", ondelete="CASCADE"), nullable=False, index=True)
    label = db.Column(db.String(300), nullable=False)
    question_type = db.Column(db.String(30), default="rating_stars", nullable=False)
    required = db.Column(db.Boolean, default=False, nullable=False)
    options_json = db.Column(db.JSON, default=list)
    position = db.Column(db.Integer, default=0)
    rating_scale = db.Column(db.Integer, default=5)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    feedback_type = db.Column(db.String(30), default="rating_stars", nullable=False)

    def get_options(self):
        """Return options as a list of ``{"value", "label"}`` dicts."""
        opts = self.options_json or []
        if isinstance(opts, list):
            result = []
            for opt in opts:
                if isinstance(opt, dict):
                    result.append({"value": opt.get("value", ""), "label": opt.get("label", "")})
                elif isinstance(opt, str):
                    result.append({"value": opt, "label": opt})
            return result
        return []

    def to_dict(self):
        return {
            "id": self.id,
            "label": self.label,
            "question_type": self.question_type,
            "required": self.required,
            "options": self.get_options(),
            "rating_scale": self.rating_scale,
            "position": self.position,
            "is_active": self.is_active,
        }


class FeedbackFormResponse(db.Model):
    """One student's fully-submitted custom feedback form (one per registration)."""
    __tablename__ = "feedback_form_response"

    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey("registration.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    template_id = db.Column(db.Integer, db.ForeignKey("feedback_form_template.id", ondelete="SET NULL"))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_anonymous = db.Column(db.Boolean, default=False, nullable=False)

    answers = db.relationship("FeedbackFormAnswer", backref="response",
                              cascade="all, delete-orphan", order_by="FeedbackFormQuestion.position")
    template = db.relationship("FeedbackFormTemplate", back_populates="responses")
    registration = db.relationship("Registration", backref="feedback_form_response")

    def get_answer_for_question(self, question_id):
        """Return the answer value (string) for a given question, or ``None``."""
        for ans in self.answers:
            if ans.question_id == question_id:
                return ans.value
        return None


class FeedbackFormAnswer(db.Model):
    """A single answer belonging to a :class:`FeedbackFormResponse`."""
    __tablename__ = "feedback_form_answer"

    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey("feedback_form_response.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("feedback_form_question.id", ondelete="SET NULL"))
    value = db.Column(db.Text)

    question = db.relationship("FeedbackFormQuestion", backref="answers")
