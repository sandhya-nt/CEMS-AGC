"""Transactional services used by routes and API endpoints.

Services deliberately keep gateway integrations behind small adapter functions. The
development payment adapter records a mock transaction and never accepts or stores
card, CVV, UPI PIN, or other sensitive payment credentials.
"""

import os
import re
import secrets
from datetime import datetime, timedelta
from io import BytesIO

from flask import current_app, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from .extensions import db


def utcnow():
    return datetime.utcnow()


def clean_text(value, limit=5000):
    return (value or "").strip()[:limit]


def parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def parse_time(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.time().replace(second=0, microsecond=0)
    if isinstance(value, str):
        for fmt in ("%H:%M", "%I:%M %p", "%I:%M%p"):
            try:
                return datetime.strptime(value.strip(), fmt).time()
            except ValueError:
                pass
    return None


def event_datetime(event):
    date_value = parse_date(event.date)
    time_value = parse_time(event.start_time)
    if not date_value or not time_value:
        return None
    return datetime.combine(date_value, time_value)


def available_seats(event):
    from app import Registration

    return max(
        0,
        int(event.capacity or 0)
        - Registration.query.filter(
            Registration.event_id == event.id,
            Registration.status.in_(["confirmed", "pending"]),
        ).count(),
    )


def event_display_status(event):
    """Return a user-facing status while preserving the stored workflow state."""
    status = (event.status or "draft").lower()
    aliases = {
        "pending": "pending_approval",
        "submitted": "pending_approval",
        "waiting": "pending_approval",
        "changes_requested": "changes_requested",
        "published": "approved",
    }
    status = aliases.get(status, status)
    if status in {"cancelled", "rejected", "archived", "draft", "changes_requested", "pending_approval"}:
        return status.replace("_", " ").title()
    if event.date and event.date < utcnow().date():
        return "Completed"
    now = utcnow()
    start = event_datetime(event)
    end_time = parse_time(event.end_time)
    end = datetime.combine(event.date, end_time) if event.date and end_time else None
    if start and end and start <= now <= end:
        return "Ongoing"
    if available_seats(event) <= 0:
        return "Full"
    deadline = parse_date(event.registration_deadline)
    if deadline and now.date() > deadline:
        return "Registration Closed"
    return "Registration Open"


def audit(actor=None, action="", entity_type="", entity_id=None, description="", metadata=None, actor_role=None):
    from app import AuditLog

    actor = actor if actor is not None else (current_user if current_user.is_authenticated else None)
    row = AuditLog(
        actor_id=actor.id if actor and hasattr(actor, "id") else None,
        actor_role=actor_role or (actor.role if actor and hasattr(actor, "role") else None),
        action=clean_text(action, 80),
        entity_type=clean_text(entity_type, 80),
        entity_id=entity_id,
        description=clean_text(description, 4000) or action,
        metadata_json=metadata or {},
        ip_address=request.remote_addr if request else None,
    )
    db.session.add(row)
    return row


def notify(user_id, title, message, category="general", action_url=None):
    from app import Notification

    row = Notification(
        user_id=user_id,
        title=clean_text(title, 180),
        message=clean_text(message, 4000),
        category=category,
        action_url=action_url,
        is_read=False,
    )
    db.session.add(row)
    return row


def save_uploaded_file(upload, folder, allowed_extensions, max_bytes, image=False):
    """Validate and persist one upload under static/uploads using a random filename."""
    from PIL import Image, UnidentifiedImageError

    if upload is None or not upload.filename:
        raise ValueError("No file was selected.")
    filename = secure_filename(upload.filename)
    if not filename or "." not in filename:
        raise ValueError("The selected file has an invalid name.")
    extension = filename.rsplit(".", 1)[1].lower()
    if extension not in {item.lower() for item in allowed_extensions}:
        raise ValueError(f"File type .{extension} is not allowed.")
    upload.seek(0, 2)
    size = upload.tell()
    upload.seek(0)
    if size <= 0 or size > max_bytes:
        raise ValueError(f"File size must be between 1 byte and {max_bytes // (1024 * 1024)}MB.")
    if image:
        try:
            with Image.open(BytesIO(upload.read())) as verified:
                verified.verify()
            upload.seek(0)
        except (UnidentifiedImageError, OSError):
            raise ValueError("The uploaded file is not a valid image.")
    safe_folder = secure_filename(folder)
    if not safe_folder or safe_folder in {".", ".."}:
        raise ValueError("Invalid upload folder.")
    target_folder = os.path.join("static", "uploads", safe_folder)
    os.makedirs(target_folder, exist_ok=True)
    random_name = secrets.token_hex(12)
    path = os.path.join("uploads", safe_folder, f"{random_name}_{filename}")
    upload.save(os.path.join("static", path))
    return path


def validate_event_payload(data, existing=None):
    """Validate event fields before insertion or update and return normalized values."""
    required = ["title", "category", "date", "start_time", "end_time", "venue", "capacity"]
    errors = {}
    for field in required:
        if not clean_text(data.get(field, "")):
            errors[field] = "This field is required."
    title = clean_text(data.get("title", ""), 180)
    category = clean_text(data.get("category", ""), 80)
    venue = clean_text(data.get("venue", ""), 160)
    try:
        event_date = parse_date(data.get("date"))
        start = parse_time(data.get("start_time"))
        end = parse_time(data.get("end_time"))
        capacity = int(data.get("capacity", 0))
        fee = float(data.get("fee", 0) or 0)
        registration_deadline = parse_date(data.get("registration_deadline"))
        registration_start = parse_date(data.get("registration_start"))
    except (TypeError, ValueError):
        event_date = start = end = registration_deadline = registration_start = None
        capacity = fee = 0
        errors["date"] = "Enter valid date, time, capacity, and fee values."
    if start is None and data.get("start_time"):
        errors["start_time"] = "Enter a valid start time."
    if end is None and data.get("end_time"):
        errors["end_time"] = "Enter a valid end time."
    if event_date and event_date < utcnow().date() and existing is None:
        errors["date"] = "Event date cannot be in the past."
    if start and end and end <= start:
        errors["end_time"] = "End time must be after start time."
    if capacity <= 0:
        errors["capacity"] = "Capacity must be a positive number."
    if fee < 0:
        errors["fee"] = "Fee cannot be negative."
    if registration_deadline and event_date and registration_deadline > event_date:
        errors["registration_deadline"] = "Registration deadline cannot be after the event date."
    if registration_start and registration_deadline and registration_start > registration_deadline:
        errors["registration_start"] = "Registration start cannot be after the deadline."
    if data.get("event_type") not in ("free", "paid"):
        errors["event_type"] = "Choose Free or Paid."
    if errors.get("event_type") is None and fee > 0 and data.get("event_type") == "free":
        errors["event_type"] = "Paid events must use the Paid payment type."
    normalized = {
        "title": title,
        "category": category,
        "venue": venue,
        "date": event_date,
        "start_time": data.get("start_time", "").strip(),
        "end_time": data.get("end_time", "").strip(),
        "capacity": capacity,
        "fee": fee,
        "registration_deadline": registration_deadline,
        "registration_start": registration_start,
        "event_type": data.get("event_type", "free"),
    }
    return normalized, errors


def ensure_ticket(registration):
    from app import Ticket

    if registration.ticket_record:
        return registration.ticket_record
    ticket = Ticket(
        registration_id=registration.id,
        qr_token=secrets.token_urlsafe(32),
        status="active",
    )
    db.session.add(ticket)
    db.session.flush()
    return ticket


def schedule_registration_reminders(registration):
    from app import Reminder

    start = event_datetime(registration.event)
    if not start:
        return
    for reminder_type, hours in (("24_hours", 24), ("1_hour", 1)):
        scheduled = start - timedelta(hours=hours)
        if scheduled >= utcnow():
            db.session.add(
                Reminder(
                    event_id=registration.event_id,
                    user_id=registration.user_id,
                    registration_id=registration.id,
                    reminder_type=reminder_type,
                    scheduled_at=scheduled,
                    channel="dashboard",
                    status="scheduled",
                )
            )


def register_student(event, user, custom_answers=None, terms_accepted=False):
    """Create a registration atomically with a ticket and custom responses."""
    from app import EventCustomField, EventCustomResponse, Registration, Ticket

    normalized_status = (event.status or "").lower()
    if normalized_status not in {"approved", "published"}:
        raise ValueError("This event is not available for registration.")
    if user.role != "student" or not user.is_active_account:
        raise ValueError("Your account cannot register for events.")
    if Registration.query.filter(
        Registration.event_id == event.id,
        Registration.user_id == user.id,
        Registration.status != "cancelled",
    ).first():
        raise ValueError("You are already registered for this event.")
    if available_seats(event) <= 0:
        raise ValueError("This event is full.")
    deadline = parse_date(event.registration_deadline)
    if deadline and utcnow().date() > deadline:
        raise ValueError("Registration deadline has passed.")
    if event.date and event.date < utcnow().date():
        raise ValueError("This event has already taken place.")
    if not terms_accepted:
        raise ValueError("Please accept the event terms before registering.")
    if event.fee > 0:
        raise ValueError("Paid event registration must continue through payment.")

    registration = Registration(
        ticket_code="AGC-" + secrets.token_hex(6).upper(),
        user_id=user.id,
        event_id=event.id,
        status="confirmed",
        payment_status="free",
        terms_accepted=True,
    )
    db.session.add(registration)
    db.session.flush()
    db.session.add(Ticket(registration_id=registration.id, qr_token=secrets.token_urlsafe(32), status="active"))
    fields = EventCustomField.query.filter_by(event_id=event.id).order_by(EventCustomField.position).all()
    supplied = custom_answers or {}
    for field in fields:
        value = clean_text(supplied.get(str(field.id) or field.label, ""), 2000)
        if field.required and not value:
            raise ValueError(f"{field.label} is required.")
        if value:
            db.session.add(EventCustomResponse(registration_id=registration.id, field_id=field.id, value=value))
    schedule_registration_reminders(registration)
    notify(user.id, "Registration confirmed", f"You are registered for {event.title}.", "registration", url_for("ticket", registration_id=registration.id))
    audit(user, "registration.created", "Registration", registration.id, f"{user.name} registered for {event.title}.")
    db.session.commit()
    return registration


def create_mock_payment(registration, payment_method="mock"):
    from app import Payment

    if registration.event.fee <= 0:
        raise ValueError("This event is free.")
    if registration.payment_record:
        raise ValueError("A payment already exists for this registration.")
    transaction_id = "MOCK-" + secrets.token_urlsafe(18)
    payment = Payment(
        registration_id=registration.id,
        amount=registration.event.fee,
        currency="INR",
        provider="mock",
        provider_payment_id=transaction_id,
        transaction_id=transaction_id,
        payment_method=payment_method,
        status="successful",
        raw_response_json={"mode": "development", "sensitive_data_stored": False},
        paid_at=utcnow(),
    )
    registration.status = "confirmed"
    registration.payment_status = "paid"
    db.session.add(payment)
    notify(registration.user_id, "Payment successful", f"Mock payment for {registration.event.title} was recorded.", "payment", url_for("ticket", registration_id=registration.id))
    audit(registration.user, "payment.successful", "Payment", payment.id, f"Mock payment recorded for {registration.event.title}.")
    db.session.commit()
    return payment


def mark_attendance(identifier, organizer):
    from app import AttendanceRecord, Registration, Ticket

    identifier = (identifier or "").strip()
    code = identifier.upper()
    registration = None
    if identifier:
        ticket = Ticket.query.filter_by(qr_token=identifier).first()
        if ticket:
            registration = ticket.registration
        if registration is None:
            registration = Registration.query.filter_by(ticket_code=code).first()
    if not registration:
        raise LookupError("Ticket not found.")
    if registration.event.organizer_id != organizer.id:
        raise PermissionError("This ticket belongs to another organizer.")
    if registration.status != "confirmed":
        raise ValueError("This ticket is not active.")
    if registration.attended:
        return registration, True
    if registration.event.status not in {"approved", "published"}:
        raise ValueError("This event is not active.")
    registration.attended = True
    registration.checkin_time = utcnow()
    db.session.add(
        AttendanceRecord(
            registration_id=registration.id,
            check_in_time=registration.checkin_time,
            method="qr_scan",
            status="checked_in",
        )
    )
    notify(registration.user_id, "Attendance marked", f"Your attendance was marked for {registration.event.title}.", "attendance", url_for("my_registrations"))
    audit(organizer, "attendance.marked", "Attendance", registration.id, f"{registration.user.name} checked in for {registration.event.title}.")
    db.session.commit()
    return registration, False


def cancel_registration(registration, actor, reason=""):
    from app import EventWaitlist, Ticket

    if registration.status == "cancelled":
        raise ValueError("Registration is already cancelled.")
    registration.status = "cancelled"
    if registration.ticket_record:
        registration.ticket_record.status = "revoked"
        registration.ticket_record.revoked_reason = clean_text(reason, 500)
        registration.ticket_record.revoked_at = utcnow()
    notify(registration.user_id, "Registration cancelled", f"Your registration for {registration.event.title} was cancelled.", "registration")
    audit(actor, "registration.cancelled", "Registration", registration.id, reason or f"{registration.user.name} cancelled {registration.event.title}.")
    db.session.commit()
    process_waitlist(registration.event)


def process_waitlist(event):
    from app import EventWaitlist, Registration, Ticket

    if available_seats(event) <= 0:
        return None
    waiting = EventWaitlist.query.filter_by(event_id=event.id, status="waiting").order_by(EventWaitlist.waitlist_position).first()
    if not waiting:
        return None
    registration = Registration(
        ticket_code="AGC-" + secrets.token_hex(6).upper(),
        user_id=waiting.user_id,
        event_id=event.id,
        status="confirmed",
        payment_status="free" if event.fee <= 0 else "pending",
        terms_accepted=True,
    )
    db.session.add(registration)
    db.session.flush()
    db.session.add(Ticket(registration_id=registration.id, qr_token=secrets.token_urlsafe(32), status="active"))
    waiting.status = "promoted"
    notify(waiting.user_id, "Waitlist promoted", f"A seat is now available for {event.title}.", "registration", url_for("ticket", registration_id=registration.id))
    audit(None, "waitlist.promoted", "Registration", registration.id, f"Waitlist seat promoted for {event.title}.")
    db.session.commit()
    return registration


def send_due_reminders():
    from app import Reminder

    due = Reminder.query.filter(Reminder.status == "scheduled", Reminder.scheduled_at <= utcnow()).all()
    delivered = 0
    for reminder in due:
        if reminder.channel == "email":
            try:
                from app import send_email

                ok = send_email(reminder.user.email, f"Event reminder: {reminder.event.title}", reminder.delivery_message or "An event you registered for is coming up.")
            except Exception:
                ok = False
            if not ok:
                reminder.status = "failed"
                continue
        else:
            notify(
                reminder.user_id,
                "Event reminder",
                reminder.delivery_message or f"Reminder: {reminder.event.title} is coming up.",
                "reminder",
                url_for("event_details", event_id=reminder.event_id),
            )
        reminder.status = "sent"
        reminder.sent_at = utcnow()
        delivered += 1
    if due:
        db.session.commit()
    return delivered


def event_history(event):
    from app import EventActivity, EventApprovalHistory

    approvals = EventApprovalHistory.query.filter_by(event_id=event.id).order_by(EventApprovalHistory.created_at.desc()).all()
    activities = EventActivity.query.filter_by(event_id=event.id).order_by(EventActivity.created_at.desc()).all()
    return approvals + activities


def parse_custom_questions(raw):
    """Parse organizer custom questions from JSON or newline-separated labels."""
    import json

    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        value = json.loads(raw)
        if isinstance(value, list):
            return value
    except (TypeError, ValueError):
        pass
    return [{"label": clean_text(line, 180), "field_type": "text", "required": False} for line in raw.splitlines() if clean_text(line)]
