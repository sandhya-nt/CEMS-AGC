"""Relational domain models for workflows not represented by the legacy app schema."""

from datetime import datetime

from .extensions import db


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
    course = db.Column(db.String(120))
    semester = db.Column(db.String(30))
    profile_image = db.Column(db.String(255))
    bio = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("student_profile", uselist=False))


class OrganizerProfile(db.Model):
    __tablename__ = "organizer_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), unique=True, nullable=False)
    employee_id = db.Column(db.String(80), unique=True)
    title = db.Column(db.String(120))
    department = db.Column(db.String(120))
    bio = db.Column(db.Text)
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
    field_type = db.Column(db.String(30), default="text")
    required = db.Column(db.Boolean, default=False)
    options_json = db.Column(db.JSON, default=list)
    position = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    event = db.relationship("Event", backref="custom_fields")


class EventCustomResponse(db.Model):
    __tablename__ = "event_custom_response"

    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey("registration.id", ondelete="CASCADE"), nullable=False, index=True)
    field_id = db.Column(db.Integer, db.ForeignKey("event_custom_field.id", ondelete="CASCADE"), nullable=False)
    value = db.Column(db.Text, nullable=False)
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
