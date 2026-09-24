"""Transactional services used by routes and API endpoints.

Services deliberately keep gateway integrations behind small adapter functions. The
development payment adapter records a mock transaction and never accepts or stores
card, CVV, UPI PIN, or other sensitive payment credentials.
"""

import json
import os
import re
import secrets
from collections import Counter
from datetime import date, datetime, timedelta
from io import BytesIO

from flask import current_app, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from .extensions import db


# ==============================
# FACULTY ADMIN PERMISSIONS
# ==============================

def is_faculty_admin(user=None):
    """Check if a user is a Faculty Admin with elevated privileges."""
    user = user or current_user
    if not user or not user.is_authenticated:
        return False
    if user.role != "teacher":
        return False
    profile = getattr(user, "faculty_profile", None)
    return profile and profile.is_faculty_admin


def faculty_admin_has_permission(permission: str, user=None) -> bool:
    """Check if a faculty admin has a specific permission."""
    user = user or current_user
    if not is_faculty_admin(user):
        return False
    profile = getattr(user, "faculty_profile", None)
    if not profile:
        return False
    return profile.has_permission(permission)


def require_faculty_admin_permission(permission: str):
    """Decorator to require a specific faculty admin permission."""
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if not faculty_admin_has_permission(permission):
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def get_faculty_admin_profile(user=None):
    """Get the faculty admin profile for a user, if they are a faculty admin."""
    user = user or current_user
    if not is_faculty_admin(user):
        return None
    return getattr(user, "faculty_profile", None)


def utcnow():
    return datetime.utcnow()


def clean_text(value, limit=5000):
    return (value or "").strip()[:limit]


def parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
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
            Registration.status.in_(["confirmed", "pending", "approved"]),
        ).count(),
    )


def event_display_status(event):
    """Return a user-facing status while preserving the stored workflow state."""
    status = (event.status or "draft").lower()
    # Workflow statuses short-circuit — they take priority over runtime checks
    if status in ("cancelled", "cancellation_requested", "reschedule_requested"):
        return workflow_status(event)
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


def notify(user_id, title, message, category="general", action_url=None, event_id=None, priority="normal", expires_at=None):
    from app import Notification

    row = Notification(
        user_id=user_id,
        title=clean_text(title, 180),
        message=clean_text(message, 4000),
        category=category,
        action_url=action_url,
        event_id=event_id,
        priority=priority,
        expires_at=expires_at,
        is_read=False,
    )
    db.session.add(row)
    return row


def notify_notice_published(notice):
    """Broadcast a notification to every student and faculty when a notice is published.

    Only sends to users who have not already been notified for this notice
    (idempotent on re-publish).  Uses the ``notice`` category registered in
    ``NOTIFICATION_CATEGORIES``.
    """
    from app import User, AccountStatus

    title = getattr(notice, "title", "New College Notice")
    excerpt = (notice.description or "")[:200]
    action_url = url_for("board_notice_detail", notice_id=notice.id)

    recipients = (
        db.session.query(User.id)
        .filter(User.role.in_(("student", "faculty")))
        .filter(User.account_status == AccountStatus.ACTIVE)
        .all()
    )

    for (uid,) in recipients:
        notify(
            uid,
            title,
            excerpt or "A new college notice has been published.",
            "notice",
            action_url,
            getattr(notice, "event_id", None),
        )


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


def save_secure_resource_file(upload, folder, allowed_extensions, allowed_mime_types, max_bytes,
                              blocked_extensions=None, detect_mime=True):
    """Hardened file upload with extension, MIME, size, executable and path-traversal checks.

    Returns a dict: {"path": str, "filename": str, "size": int, "mime_type": str, "extension": str}
    Raises ValueError on any validation failure.
    """
    import mimetypes

    from app import ALLOWED_RESOURCE_MIME_TYPES, BLOCKED_RESOURCE_EXTENSIONS

    blocked = set(blocked_extensions or BLOCKED_RESOURCE_EXTENSIONS)
    allowed = {e.lower() for e in allowed_extensions}
    allowed_mime = {m.lower() for m in allowed_mime_types}

    if upload is None or not getattr(upload, "filename", ""):
        raise ValueError("No file was selected.")
    original = secure_filename(upload.filename)
    if not original or "." not in original:
        raise ValueError("The selected file has an invalid name.")
    extension = original.rsplit(".", 1)[1].lower()
    if extension in blocked:
        raise ValueError(f"File type .{extension} is blocked for security reasons.")
    if extension not in allowed:
        raise ValueError(f"File type .{extension} is not allowed. Allowed: {', '.join(sorted(allowed))}")

    upload.seek(0, 2)
    size = upload.tell()
    upload.seek(0)
    if size <= 0 or size > max_bytes:
        raise ValueError(f"File size must be between 1 byte and {max_bytes // (1024 * 1024)}MB.")

    declared_mime = (getattr(upload, "mimetype", "") or "").lower()
    if detect_mime:
        detected = (mimetypes.guess_type(original)[0] or "").lower()
        effective_mime = detected or declared_mime
        if effective_mime and effective_mime not in allowed_mime:
            raise ValueError(f"MIME type '{effective_mime}' is not permitted.")
    else:
        effective_mime = declared_mime or "application/octet-stream"

    # Image verification: actually open and verify the image with PIL
    if image:
        from PIL import Image, UnidentifiedImageError
        upload.seek(0)
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
    random_name = secrets.token_hex(16)
    safe_path = os.path.join("uploads", safe_folder, f"{random_name}_{original}")
    abs_path = os.path.join("static", safe_path)
    # Final path-traversal guard: ensure resolved path stays inside static/uploads/<folder>
    real_target = os.path.realpath(target_folder)
    real_abs = os.path.realpath(abs_path)
    if not real_abs.startswith(real_target + os.sep) and real_abs != real_target:
        raise ValueError("Invalid upload path detected.")
    upload.save(abs_path)
    return {
        "path": safe_path,
        "filename": original,
        "size": size,
        "mime_type": effective_mime,
        "extension": extension,
    }


def validate_external_url(url):
    """Reject javascript/data URLs and other non-http(s) schemes."""
    if not url:
        raise ValueError("URL is required.")
    value = url.strip()
    lowered = value.lower()
    if lowered.startswith(("javascript:", "data:", "file:", "vbscript:")):
        raise ValueError("That URL scheme is not allowed.")
    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        raise ValueError("Only http/https URLs are allowed.")
    return value


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
        "target_department": clean_text(data.get("target_department", ""), 120),
        "target_semester": clean_text(data.get("target_semester", ""), 50),
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


def _user_matches_field(user, field_name, target_value):
    """Check if a user's profile or user model has a matching field value (case-insensitive)."""
    target_value = (target_value or "").strip().lower()
    if not target_value:
        return True

    # Check the User model directly
    user_value = getattr(user, field_name, None) or ""
    if (user_value or "").strip().lower() == target_value:
        return True

    # Fall back to StudentProfile if it exists
    try:
        profile = getattr(user, "student_profile", None)
        if profile:
            profile_value = getattr(profile, field_name, None) or ""
            if (profile_value or "").strip().lower() == target_value:
                return True
    except Exception:
        pass

    return False


def register_student(event, user, custom_answers=None, terms_accepted=False, initial_status="confirmed"):
    """Create a registration atomically with a ticket and custom responses."""
    from app import EventCustomField, EventCustomResponse, Registration, Ticket, AccountStatus

    normalized_status = (event.status or "").lower()
    if normalized_status not in {"approved", "published"}:
        raise ValueError("This event is not available for registration.")
    if user.role != "student" or user.account_status != AccountStatus.ACTIVE:
        raise ValueError("Your account cannot register for events.")
    # Eligibility: target_department and target_semester restrict the event
    if event.target_department:
        target_dept = (event.target_department or "").strip().lower()
        if target_dept and not _user_matches_field(user, "department", target_dept):
            raise ValueError(
                f"This event is restricted to the {event.target_department} department."
            )
    if event.target_semester:
        target_sem = (event.target_semester or "").strip().lower()
        if target_sem and not _user_matches_field(user, "semester", target_sem):
            raise ValueError(
                f"This event is restricted to students in the {event.target_semester} semester."
            )
    if Registration.query.filter(
        Registration.event_id == event.id,
        Registration.user_id == user.id,
        Registration.status != "cancelled",
    ).first():
        raise ValueError("You are already registered for this event.")
    # Registration window
    reg_start = parse_date(event.registration_start)
    if reg_start and utcnow().date() < reg_start:
        raise ValueError("Registration is not yet open.")
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

    # Remove any stale cancelled registration so the unique constraint on
    # (user_id, event_id) does not block a fresh registration.
    stale_cancelled = Registration.query.filter(
        Registration.event_id == event.id,
        Registration.user_id == user.id,
        Registration.status == "cancelled",
    ).first()
    if stale_cancelled:
        db.session.delete(stale_cancelled)

    registration = Registration(
        ticket_code="AGC-" + secrets.token_hex(6).upper(),
        user_id=user.id,
        event_id=event.id,
        status=initial_status,
        payment_status="free" if event.fee <= 0 else "pending",
        terms_accepted=True,
    )
    db.session.add(registration)
    db.session.flush()
    db.session.add(Ticket(registration_id=registration.id, qr_token=secrets.token_urlsafe(32), status="active"))
    
    # Process custom fields with validation
    fields = EventCustomField.query.filter_by(event_id=event.id, is_active=True).order_by(EventCustomField.position).all()
    supplied = custom_answers or {}
    errors = []
    
    for field in fields:
        field_id = str(field.id)
        value = clean_text(supplied.get(field_id, ""), 2000)
        
        # Check required
        if field.required and not value:
            errors.append(f"{field.label} is required.")
            continue
            
        # Validate based on field type and validation rules
        if value:
            validation_error = _validate_field_value(field, value)
            if validation_error:
                errors.append(f"{field.label}: {validation_error}")
                continue
                
            db.session.add(EventCustomResponse(registration_id=registration.id, field_id=field.id, value=value))
    
    if errors:
        db.session.rollback()
        raise ValueError("; ".join(errors))
    
    schedule_registration_reminders(registration)
    notify(user.id, "Registration confirmed", f"You are registered for {event.title}.", "registration_confirmation", url_for("ticket", registration_id=registration.id), event.id)
    audit(user, "registration.created", "Registration", registration.id, f"{user.name} registered for {event.title}.")
    db.session.commit()
    return registration


# ---------------------------------------------------------------------------
# Registration eligibility helpers
# ---------------------------------------------------------------------------

def _registration_state_label(status):
    """Human-readable suffix describing a registration's lifecycle state."""
    labels = {
        "confirmed": "",
        "approved": " (approved)",
        "pending": " (pending approval)",
        "cancelled": " (cancelled)",
    }
    return labels.get(status, "")


def check_registration_eligibility(event, user):
    """Comprehensive pre-flight eligibility check for student event registration.

    Verifies, in order:
      1. authentication
      2. account / role eligibility (active student)
      3. event availability (rejects **rejected**, **cancelled**, and other
         unapproved — as well as **past** — events)
      4. registration window start
      5. registration deadline
      6. event capacity
      7. duplicate registration prevention
      8. structured eligibility (target department / semester)

    Returns a dict with keys::
        eligible  : bool
        reason    : str   machine-readable code
        message   : str   human-readable explanation
        status    : str   "error" | "warning" | "info" | "success"
        seats     : int   remaining seats (meaningful when eligible)
    """
    from app import AccountStatus, Registration

    result = {"eligible": False, "reason": "blocked", "message": "", "status": "error", "seats": 0}

    def block(reason, message, status="error"):
        result["reason"] = reason
        result["message"] = message
        result["status"] = status
        return result

    # 1. Authentication
    if not user or not user.is_authenticated:
        return block("not_authenticated", "Sign in to register for this event.", "info")

    # 2. Account & role eligibility
    if user.role != "student":
        return block("not_student", "Only student accounts can register for events.")
    if user.account_status != AccountStatus.ACTIVE:
        return block("account_inactive", "Your account is not active. Contact support to reactivate your account.")

    # 3. Event availability — never allow rejected / cancelled / pending / past events
    normalized_status = (event.status or "").lower()
    if normalized_status in ("rejected", "cancelled"):
        return block(
            "event_unavailable",
            f"This event has been {normalized_status} and is no longer open for registration.",
        )
    if normalized_status not in ("approved", "published"):
        return block("event_not_approved", "This event is not open for registration at this time.")

    if event.date and event.date < utcnow().date():
        return block(
            "event_past",
            f"This event was held on {event.date.strftime('%d %b %Y')} and registration is now closed.",
        )

    # 4. Registration window
    reg_start = parse_date(event.registration_start)
    if reg_start and utcnow().date() < reg_start:
        return block(
            "registration_not_open",
            f"Registration opens on {reg_start.strftime('%d %b %Y')}.",
        )

    # 5. Registration deadline
    deadline = parse_date(event.registration_deadline)
    if deadline and utcnow().date() > deadline:
        return block(
            "deadline_passed",
            f"The registration deadline was {deadline.strftime('%d %b %Y')}.",
            "warning",
        )

    # 6. Capacity
    seats = available_seats(event)
    if seats <= 0:
        return block("event_full", f"This event is full (capacity: {event.capacity}).", "warning")

    # 7. Duplicate registration prevention
    existing = Registration.query.filter(
        Registration.event_id == event.id,
        Registration.user_id == user.id,
        Registration.status != "cancelled",
    ).first()
    if existing:
        label = _registration_state_label(existing.status)
        return block(
            "already_registered",
            f"You are already registered{label} for this event.",
            "info",
        )

    # 8. Structured eligibility (department / semester targeting)
    if event.target_department:
        if not _user_matches_field(user, "department", event.target_department):
            return block("not_eligible", f"This event is restricted to: {event.target_department}.")
    if event.target_semester:
        if not _user_matches_field(user, "semester", event.target_semester):
            return block("not_eligible", f"This event is restricted to: {event.target_semester}.")

    # All checks passed
    result.update({
        "eligible": True,
        "reason": "eligible",
        "message": "",
        "status": "success",
        "seats": seats,
    })
    return result


def _validate_field_value(field, value):
    """Validate a field value based on field type and validation rules.
    Returns error message string or None if valid.
    """
    import re
    from datetime import datetime
    
    validation = field.get_validation() if hasattr(field, 'get_validation') else (field.validation_json or {})
    field_type = field.field_type
    
    # Type-specific validation
    if field_type == "email":
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
            return "Enter a valid email address."
    
    elif field_type == "phone":
        if not re.match(r"^[\d\s\-\+\(\)]{7,20}$", value):
            return "Enter a valid phone number."
    
    elif field_type == "number":
        try:
            num = float(value)
            if "min" in validation and num < float(validation["min"]):
                return f"Value must be at least {validation['min']}."
            if "max" in validation and num > float(validation["max"]):
                return f"Value must be at most {validation['max']}."
        except ValueError:
            return "Enter a valid number."
    
    elif field_type == "date":
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d").date()
            if "min" in validation:
                min_date = datetime.strptime(validation["min"], "%Y-%m-%d").date()
                if parsed < min_date:
                    return f"Date must be on or after {validation['min']}."
            if "max" in validation:
                max_date = datetime.strptime(validation["max"], "%Y-%m-%d").date()
                if parsed > max_date:
                    return f"Date must be on or before {validation['max']}."
        except ValueError:
            return "Enter a valid date (YYYY-MM-DD)."
    
    elif field_type in ("dropdown", "radio"):
        # Validate against allowed options
        allowed = [opt.get("value", "") for opt in (field.get_options() if hasattr(field, 'get_options') else field.options_json or [])]
        if allowed and value not in allowed:
            return "Select a valid option."
    
    elif field_type == "checkbox":
        # For checkboxes, value might be comma-separated
        allowed = [opt.get("value", "") for opt in (field.get_options() if hasattr(field, 'get_options') else field.options_json or [])]
        selected = [v.strip() for v in value.split(",") if v.strip()]
        for sel in selected:
            if allowed and sel not in allowed:
                return "Select valid option(s)."
    
    # Generic validation rules
    if "min_length" in validation and len(value) < int(validation["min_length"]):
        return f"Must be at least {validation['min_length']} characters."
    if "max_length" in validation and len(value) > int(validation["max_length"]):
        return f"Must be at most {validation['max_length']} characters."
    if "pattern" in validation:
        try:
            if not re.match(validation["pattern"], value):
                return validation.get("pattern_message", "Invalid format.")
        except re.error:
            pass
    
    return None


def create_mock_payment(registration, payment_method="mock"):
    """Record a simulated payment for development/testing only.

    .. warning::
        This function is intended **only** for development. It always
        records the payment as successful and tags it with ``provider="mock"``.
        It must never be used as a stand-in for a real payment gateway in
        production. Use :func:`initiate_payment` for the provider-aware
        flow that respects the configured payment provider.
    """
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
    notify(registration.user_id, "Payment successful", f"Mock payment for {registration.event.title} was recorded.", "payment_status", url_for("ticket", registration_id=registration.id), registration.event_id)
    audit(registration.user, "payment.successful", "Payment", payment.id, f"Mock payment recorded for {registration.event.title}.")
    db.session.commit()
    return payment


def initiate_payment(registration, payment_method: str):
    """Process a payment for a registration using the configured provider.

    Delegates to :func:`get_payment_provider` to obtain the active provider.
    Creates a :class:`Payment` record (in the ``payment`` table) only after
    the provider confirms the transaction.

    Raises :class:`PaymentError` (via ``ValueError`` adaptation in the route)
    when no provider is configured or the provider rejects the transaction.
    """
    from app import Payment
    from cems.payment import get_payment_provider, PaymentError

    if registration.event.fee <= 0:
        raise ValueError("This event is free.")
    if registration.payment_record:
        raise ValueError("A payment already exists for this registration.")

    provider = get_payment_provider()
    if not provider.is_available():
        raise PaymentError(
            "Payment is currently unavailable. No payment provider is configured. "
            "Contact the event organizer for alternative arrangements."
        )

    try:
        result = provider.initiate_payment(registration, payment_method)
    except PaymentError:
        raise
    except Exception as exc:
        raise PaymentError(f"Payment failed: {exc}")

    transaction_id = result.get("transaction_id") or ("TXN-" + secrets.token_urlsafe(12).upper())
    reference = result.get("reference") or transaction_id

    payment = Payment(
        registration_id=registration.id,
        amount=float(registration.event.fee),
        currency="INR",
        provider=result.get("provider", provider.display_name().lower().replace(" ", "_")),
        provider_payment_id=reference,
        transaction_id=transaction_id,
        payment_method=payment_method,
        status=result.get("status", "pending"),
        raw_response_json=result.get("raw_response_json", {}) or {},
        paid_at=utcnow() if result.get("status") == "successful" else None,
    )
    registration.status = "confirmed"
    registration.payment_status = "paid" if result.get("status") == "successful" else "pending"
    db.session.add(payment)
    notify(registration.user_id, "Payment initiated", f"Payment of ₹{registration.event.fee:.2f} initiated for {registration.event.title}. Reference: {reference}", "payment_status", url_for("ticket", registration_id=registration.id), registration.event_id)
    audit(registration.user, "payment.initiated", "Payment", payment.id, f"Payment initiated via {provider.display_name()} for {registration.event.title}. Reference: {reference}.")
    db.session.commit()
    return payment, result


def verify_payment(registration, transaction_id: str):
    """Verify a payment callback using the configured provider.

    Updates the :class:`Payment` record based on the verification result.

    Raises :class:`PaymentError` when no provider is configured or verification fails.
    """
    from app import Payment
    from cems.payment import get_payment_provider, PaymentError

    provider = get_payment_provider()
    if not provider.is_available():
        raise PaymentError("Payment is currently unavailable. No payment provider is configured.")

    result = provider.verify_payment(transaction_id)
    payment = registration.payment_record
    if payment:
        payment.status = result.get("status", "verified")
        payment.updated_at = utcnow()
        if result.get("status") == "successful" and not payment.paid_at:
            payment.paid_at = utcnow()
            registration.payment_status = "paid"
            registration.status = "confirmed"
        db.session.commit()
    return result


def payment_display_status(payment_status: str) -> str:
    """Return a human-readable payment status label."""
    status_map = {
        "free": "Free",
        "pending": "Pending",
        "awaiting_verification": "Awaiting Verification",
        "paid": "Paid",
        "successful": "Paid",
        "unavailable": "Payment Unavailable",
        "unpaid": "Unpaid",
        "failed": "Failed",
        "refunded": "Refunded",
        "cancelled": "Cancelled",
    }
    return status_map.get((payment_status or "").lower(), (payment_status or "—").title())


def payment_reference(registration) -> str:
    """Return the payment reference (transaction_id) for a registration.

    Returns ``None`` when no payment record exists (e.g. free events).
    """
    if registration.payment_record:
        return registration.payment_record.transaction_id or registration.payment_record.provider_payment_id
    return None


def normalize_attendance_status(status):
    """Normalize legacy and current attendance status values."""
    raw = str(status or "not_marked").strip().lower().replace("-", "_").replace(" ", "_")
    if raw in ("checked_in", "present", "attended", "true"):
        return "present"
    if raw in ("late", "checked_in_late"):
        return "late"
    if raw in ("absent", "not_attended", "false"):
        return "absent"
    return "not_marked"


def attendance_summary(event_id):
    """Return attendance totals for all active registrations in an event.

    ``confirmed`` is the normal post-registration status; ``approved`` is kept
    for workflows that explicitly approve a registration. Present includes
    late check-ins, while absent includes every active registration that has
    not checked in.
    """
    from app import Attendance, AttendanceRecord, Registration

    registrations = Registration.query.filter(
        Registration.event_id == event_id,
        Registration.status.in_(["confirmed", "approved"]),
    ).all()
    records = {
        record.registration_id: record
        for record in AttendanceRecord.query.filter(
            AttendanceRecord.registration_id.in_([reg.id for reg in registrations])
        ).all()
    } if registrations else {}
    legacy_records = {
        record.registration_id: record
        for record in Attendance.query.filter(
            Attendance.registration_id.in_([reg.id for reg in registrations])
        ).all()
    } if registrations else {}

    present = 0
    late = 0
    explicit_absent = 0
    not_marked = 0
    for registration in registrations:
        record = records.get(registration.id)
        legacy = legacy_records.get(registration.id)
        status = normalize_attendance_status(
            record.status if record else (legacy.status if legacy else "not_marked")
        )
        is_present = registration.attended or status in ("present", "late")
        if is_present:
            present += 1
            if status == "late":
                late += 1
        elif status == "absent":
            explicit_absent += 1
        else:
            not_marked += 1

    registered = len(registrations)
    absent = registered - present
    return {
        "registered": registered,
        "total": registered,
        "present": present,
        "absent": absent,
        "explicit_absent": explicit_absent,
        "not_marked": not_marked,
        "late": late,
        "attendance_percentage": round((present / registered * 100), 1) if registered else 0,
    }


def sync_attendance(registration, status, actor=None, method="manual", check_in_time=None):
    """Synchronize the legacy Attendance row, AttendanceRecord, and registration.

    This keeps QR check-in, faculty corrections, and reporting on one source of
    truth without creating duplicate rows for the same registration.
    """
    from app import Attendance, AttendanceRecord

    normalized = normalize_attendance_status(status)
    if normalized not in ("present", "late", "absent", "not_marked"):
        raise ValueError("Invalid attendance status.")
    if method not in ("qr_scan", "manual"):
        raise ValueError("Invalid attendance method.")

    now = check_in_time or utcnow()
    is_present = normalized in ("present", "late")
    registration.attended = is_present
    registration.checkin_time = now if is_present else None

    record = AttendanceRecord.query.filter_by(registration_id=registration.id).first()
    if record is None:
        record = AttendanceRecord(registration_id=registration.id)
        db.session.add(record)
    record.check_in_time = now if is_present else None
    record.check_out_time = None
    record.duration_minutes = None
    record.method = method
    record.status = {
        "present": "checked_in",
        "late": "late",
        "absent": "absent",
        "not_marked": "not_marked",
    }[normalized]
    record.scanned_by = actor.id if actor is not None else record.scanned_by

    legacy = Attendance.query.filter_by(registration_id=registration.id).first()
    if legacy is None:
        legacy = Attendance.query.filter_by(
            event_id=registration.event_id,
            student_id=registration.user_id,
        ).first()
    if legacy is None:
        legacy = Attendance(
            event_id=registration.event_id,
            student_id=registration.user_id,
            registration_id=registration.id,
        )
        db.session.add(legacy)
    legacy.status = normalized
    legacy.updated_at = now
    db.session.flush()
    return normalized


def record_attendance(registration, actor, event_id=None, method="manual", status="present", notify_participant=True):
    """Central, transactional attendance recorder.

    This is the single entry point used by the QR kiosk, the organizer check-in
    flow, and the faculty attendance endpoints. It enforces every business rule
    before writing:

      * the ticket is present and active (not revoked);
      * the participant is a student;
      * the registration is confirmed/approved;
      * the event is open for check-in (approved/published);
      * the supplied ``event_id`` (if any) matches the ticket's event;
      * the actor is authorized to mark attendance for the event.

    Deduplication is enforced at two levels:

      1. A fast pre-check on ``AttendanceRecord`` / ``Registration.attended``.
      2. The ``AttendanceRecord.registration_id`` unique constraint, which makes
         concurrent scans atomic even under the SQLite default isolation level.

    On success the canonical ``AttendanceRecord`` is created or updated (with the
    legacy ``Attendance`` row and the ``Registration.attended``/``checkin_time``
    flags kept in sync via :func:`sync_attendance`), a notification is sent to
    the participant, and an audit entry is written.

    Returns ``(registration, already_attended)`` where ``already_attended`` is
    ``True`` when the participant was already marked present/late and no new
    check-in was recorded.
    """
    from app import AttendanceRecord, Registration, Event

    if registration is None:
        raise LookupError("Ticket not found.")

    registration = Registration.query.get(registration.id)
    if registration is None:
        raise LookupError("Ticket not found.")

    event = registration.event
    if event is None:
        raise LookupError("Ticket not found.")

    # Event scope check
    if event_id is not None:
        try:
            event_id = int(event_id)
        except (TypeError, ValueError):
            raise ValueError("Invalid event selection.")
        if event.id != event_id:
            raise PermissionError("This ticket does not belong to the selected event.")

    # Actor authorization
    if not _actor_authorized_for_event(actor, event):
        raise PermissionError("Not authorized to mark attendance for this event.")

    # Ticket validity
    ticket = registration.ticket_record
    if ticket is None:
        ticket = ensure_ticket(registration)
        db.session.flush()
    if ticket.status != "active" or ticket.revoked_at:
        raise ValueError("This ticket is no longer valid.")

    # Participant must be a student
    if registration.user.role != "student":
        raise ValueError("Attendance is only valid for student participants.")

    # Registration / event state checks
    if registration.status not in ("confirmed", "approved"):
        raise ValueError("This ticket is not active.")
    if event.status not in {"approved", "published"}:
        raise ValueError("This event is not active.")

    # Normalize the requested status
    normalized = normalize_attendance_status(status)
    if normalized not in ("present", "late", "absent", "not_marked"):
        raise ValueError("Invalid attendance status.")
    if method not in ("qr_scan", "manual"):
        raise ValueError("Invalid attendance method.")

    # Fast path: a checked-in record already exists for this registration.
    existing = AttendanceRecord.query.filter_by(registration_id=registration.id).first()
    if existing and normalize_attendance_status(existing.status) in ("present", "late"):
        registration.attended = True
        registration.checkin_time = existing.check_in_time or registration.checkin_time
        db.session.commit()
        return registration, True
    if normalized in ("present", "late") and registration.attended and registration.checkin_time:
        registration.attended = True
        registration.checkin_time = registration.checkin_time
        db.session.commit()
        return registration, True

    check_in_time = utcnow()
    try:
        sync_attendance(
            registration, normalized, actor=actor, method=method, check_in_time=check_in_time
        )
        db.session.commit()
    except IntegrityError:
        # A concurrent request created the row first — treat as duplicate.
        db.session.rollback()
        registration = Registration.query.get(registration.id)
        existing = AttendanceRecord.query.filter_by(registration_id=registration.id).first()
        if (
            registration and registration.attended and
            existing and normalize_attendance_status(existing.status) in ("present", "late")
        ):
            return registration, True
        raise

    if notify_participant:
        notify(
            registration.user_id, "Attendance marked",
            f"Your attendance was marked for {event.title}.",
            "attendance", url_for("my_registrations"), event.id,
        )
    audit(
        actor, "attendance.marked", "AttendanceRecord",
        existing.id if existing else registration.id,
        f"{registration.user.name} checked in for {event.title} (method={method}).",
    )
    return registration, False


def mark_attendance(identifier, organizer, event_id=None):
    """Resolve a ticket code/QR token and atomically mark the participant present.

    Delegates all validation and persistence to :func:`record_attendance` so that
    the organizer check-in flow, the kiosk, and the faculty endpoints share one
    consistent set of rules and duplicate-prevention guards.
    """
    if not organizer or not hasattr(organizer, "id"):
        raise PermissionError("Attendance marking requires an authorized organizer.")
    if event_id is not None:
        try:
            event_id = int(event_id)
        except (TypeError, ValueError):
            raise ValueError("Invalid event selection.")

    identifier = (identifier or "").strip()
    registration = _resolve_registration(identifier)
    if registration is None:
        raise LookupError("Ticket not found.")

    if event_id is not None and registration.event_id != event_id:
        raise PermissionError("This ticket does not belong to the selected event.")

    return record_attendance(registration, organizer, event_id=event_id, method="qr_scan")


def kiosk_authorized_events(actor):
    """Return events the actor is authorized to run kiosk check-in for.

    - admin: all approved/published events
    - organizer: events they own
    - teacher: events they organize OR are assigned to via EventFaculty
    """
    from app import Event, EventFaculty

    if actor.role == "admin":
        return Event.query.filter(
            Event.status.in_(["approved", "published"])
        ).order_by(Event.date.desc()).all()
    if actor.role == "organizer":
        return Event.query.filter_by(organizer_id=actor.id).filter(
            Event.status.in_(["approved", "published"])
        ).order_by(Event.date.desc()).all()
    if actor.role == "teacher":
        owned = Event.query.filter_by(organizer_id=actor.id).with_entities(Event.id).all()
        event_ids = {row[0] for row in owned}
        assigned = EventFaculty.query.filter_by(faculty_id=actor.id).with_entities(EventFaculty.event_id).all()
        for row in assigned:
            event_ids.add(row[0])
        if not event_ids:
            return []
        return Event.query.filter(
            Event.id.in_(event_ids),
            Event.status.in_(["approved", "published"]),
        ).order_by(Event.date.desc()).all()
    return []


def kiosk_attendance_count(event_id):
    """Return the live count of checked-in attendees for an event."""
    from app import AttendanceRecord, Registration

    return AttendanceRecord.query.join(Registration, AttendanceRecord.registration_id == Registration.id
    ).filter(
        Registration.event_id == event_id,
        AttendanceRecord.status == "checked_in",
    ).count()


def _resolve_registration(identifier):
    """Look up a Registration by qr_token or ticket_code (case-insensitive)."""
    from app import Ticket, Registration

    identifier = (identifier or "").strip()
    if not identifier:
        return None
    ticket = Ticket.query.filter_by(qr_token=identifier).first()
    if ticket and ticket.registration:
        return ticket.registration
    code = identifier.upper()
    return Registration.query.filter_by(ticket_code=code).first()


def _actor_authorized_for_event(actor, event):
    """Return True if *actor* may run check-in for *event*."""
    if actor.role == "admin":
        return True
    if actor.role == "organizer":
        return event.organizer_id == actor.id
    if actor.role == "teacher":
        from app import EventFaculty
        if event.organizer_id == actor.id:
            return True
        return EventFaculty.query.filter_by(
            event_id=event.id, faculty_id=actor.id
        ).first() is not None
    return False


def kiosk_checkin(identifier, event_id, actor, method="qr_scan"):
    """Atomically mark attendance at the kiosk for a single event.

    Performs full validation (ticket → event → actor authorization →
    registration status) and then records the check-in using the
    ``AttendanceRecord.registration_id`` unique constraint as the atomic
    guard against duplicate records, even when two scans arrive
    simultaneously.

    Returns a dict with keys:
        status   – "success" | "duplicate" | "invalid"
        message  – human-readable summary
        reason   – machine-readable reason for failures
        participant, ticket_code, event, checkin_time, checkin_time_iso
    """
    from app import AttendanceRecord, Registration, Event
    from sqlalchemy.exc import IntegrityError

    event = Event.query.get(event_id)
    if event is None:
        return {"status": "invalid", "message": "Invalid Ticket", "reason": "event_not_found"}

    registration = _resolve_registration(identifier)
    if registration is None:
        return {"status": "invalid", "message": "Invalid Ticket", "reason": "ticket_not_found"}

    # Verify the ticket belongs to the selected event
    if registration.event_id != event.id:
        return {"status": "invalid", "message": "Invalid Ticket", "reason": "wrong_event"}

    # Verify actor authorization
    if not _actor_authorized_for_event(actor, event):
        return {"status": "invalid", "message": "Invalid Ticket", "reason": "unauthorized"}

    # Verify registration is active (confirmed / approved)
    if registration.status not in ("confirmed", "approved"):
        return {"status": "invalid", "message": "Invalid Ticket", "reason": "not_approved"}

    # Verify event is open for check-in
    if event.status not in {"approved", "published"}:
        return {"status": "invalid", "message": "Invalid Ticket", "reason": "event_inactive"}

    # Fast path: check if already checked in via DB record
    existing = AttendanceRecord.query.filter_by(
        registration_id=registration.id, status="checked_in"
    ).first()
    check_in_time = existing.check_in_time if existing else registration.checkin_time
    if existing or (registration.attended and check_in_time):
        check_in_time = check_in_time or utcnow()
        return {
            "status": "duplicate",
            "message": "Already Checked In",
            "reason": "already_attended",
            "participant": registration.user.name,
            "ticket_code": registration.ticket_code,
            "event": event.title,
            "checkin_time": check_in_time.strftime('%d %b %Y %I:%M %p'),
            "checkin_time_iso": check_in_time.isoformat(),
        }

    # Atomic insert — the unique constraint on registration_id prevents
    # duplicates even if two concurrent requests reach this point.
    check_in_time = utcnow()
    try:
        record = AttendanceRecord(
            registration_id=registration.id,
            check_in_time=check_in_time,
            method=method,
            status="checked_in",
            scanned_by=actor.id,
        )
        db.session.add(record)
        registration.attended = True
        registration.checkin_time = check_in_time
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        # A concurrent scan beat us — fetch the winner's record
        existing = AttendanceRecord.query.filter_by(
            registration_id=registration.id
        ).first()
        check_in_time = existing.check_in_time if existing else registration.checkin_time
        check_in_time = check_in_time or utcnow()
        return {
            "status": "duplicate",
            "message": "Already Checked In",
            "reason": "already_attended",
            "participant": registration.user.name,
            "ticket_code": registration.ticket_code,
            "event": event.title,
            "checkin_time": check_in_time.strftime('%d %b %Y %I:%M %p'),
            "checkin_time_iso": check_in_time.isoformat(),
        }

    notify(
        registration.user_id, "Attendance marked",
        f"Your attendance was marked for {event.title}.",
        "attendance", url_for("my_registrations"),
    )
    audit(
        actor, "attendance.marked", "AttendanceRecord", record.id,
        f"{actor.name} checked in {registration.user.name} for {event.title} via kiosk.",
    )

    return {
        "status": "success",
        "message": "Attendance Marked",
        "reason": None,
        "participant": registration.user.name,
        "ticket_code": registration.ticket_code,
        "event": event.title,
        "checkin_time": check_in_time.strftime('%d %b %Y %I:%M %p'),
        "checkin_time_iso": check_in_time.isoformat(),
        "method": method,
    }


def approve_participant(registration_id, organizer):
    """Approve a pending/waitlisted registration for an event.

    Returns the updated Registration object.
    Raises ValueError if the registration cannot be approved.
    """
    from app import Registration, EventWaitlist, Notification, Ticket

    registration = Registration.query.get(registration_id)
    if registration is None:
        raise ValueError("Registration not found.")
    event = registration.event
    if event.organizer_id != organizer.id:
        raise ValueError("You are not authorized to manage this event's registrations.")
    if registration.status not in ("pending", "waitlisted"):
        raise ValueError(f"Registration is already {registration.status} and cannot be approved.")
    if registration.status == "waitlisted":
        current_approved = Registration.query.filter(
            Registration.event_id == event.id,
            Registration.status.in_(["pending", "approved"]),
        ).count()
        if current_approved >= event.capacity:
            raise ValueError("Event capacity is full. Cannot promote from waitlist.")
    registration.status = "approved"
    db.session.commit()
    notify(registration.user_id, "Registration Approved",
           f"Your registration for '{event.title}' has been approved.",
           "registration_approved", url_for("my_registrations"), event.id)
    audit(organizer, "registration.approved", "Registration", registration.id,
          f"Approved {registration.user.name} for {event.title}.")
    return registration


def reject_participant(registration_id, organizer, reason=""):
    """Reject a pending registration for an event.

    Returns the updated Registration object.
    Raises ValueError if the registration cannot be rejected.
    """
    from app import Registration, Notification, Ticket

    registration = Registration.query.get(registration_id)
    if registration is None:
        raise ValueError("Registration not found.")
    event = registration.event
    if event.organizer_id != organizer.id:
        raise ValueError("You are not authorized to manage this event's registrations.")
    if registration.status in ("approved", "confirmed"):
        raise ValueError("Approved registrations cannot be rejected from the organizer dashboard.")
    if registration.status == "cancelled":
        raise ValueError("Registration is already cancelled.")
    registration.status = "rejected"
    registration.cancellation_reason = clean_text(reason, 500)
    db.session.commit()
    notify(registration.user_id, "Registration Rejected",
           f"Your registration for '{event.title}' was rejected." + (f" Reason: {reason}" if reason else ""),
           "event_rejection", url_for("my_registrations"), event.id)
    audit(organizer, "registration.rejected", "Registration", registration.id,
          f"Rejected {registration.user.name} for {event.title}. {reason}")
    return registration


def cancel_participant(registration_id, organizer, reason=""):
    """Cancel a confirmed/pending registration for an event.

    Returns the updated Registration object.
    Raises ValueError if the registration cannot be cancelled.
    """
    from app import Registration, EventWaitlist, Notification, Ticket

    registration = Registration.query.get(registration_id)
    if registration is None:
        raise ValueError("Registration not found.")
    event = registration.event
    if event.organizer_id != organizer.id:
        raise ValueError("You are not authorized to manage this event's registrations.")
    if registration.status == "cancelled":
        raise ValueError("Registration is already cancelled.")
    if registration.status in ("rejected",):
        raise ValueError("Rejected registrations cannot be cancelled.")
    cancel_registration(registration, organizer, reason or "Cancelled by organizer.")
    return registration


def mark_participant_attendance(registration_id, organizer, method="manual"):
    """Mark attendance for a specific registration by ID.

    Returns the updated Registration object.
    Raises ValueError if attendance cannot be marked.
    """
    from app import AttendanceRecord, Registration, Ticket

    registration = Registration.query.get(registration_id)
    if registration is None:
        raise ValueError("Registration not found.")
    event = registration.event
    if event.organizer_id != organizer.id:
        raise ValueError("You are not authorized to manage this event's attendance.")
    if registration.status not in ("confirmed", "approved"):
        raise ValueError("Only confirmed/approved registrations can have attendance marked.")
    if registration.attended:
        return registration, True
    registration.attended = True
    registration.checkin_time = utcnow()
    db.session.add(AttendanceRecord(
        registration_id=registration.id,
        check_in_time=registration.checkin_time,
        method=method,
        status="checked_in",
        scanned_by=organizer.id,
    ))
    db.session.commit()
    notify(registration.user_id, "Attendance marked",
           f"Your attendance was marked for {event.title}.",
           "event_reminder", url_for("my_registrations"), event.id)
    audit(organizer, "attendance.marked", "Attendance", registration.id,
          f"{organizer.name} marked attendance for {registration.user.name} at {event.title}.")
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
    notify(registration.user_id, "Registration cancelled", f"Your registration for {registration.event.title} was cancelled.", "registration_cancellation", url_for("my_registrations"), registration.event_id)
    audit(actor, "registration.cancelled", "Registration", registration.id, reason or f"{registration.user.name} cancelled {registration.event.title}.")
    db.session.commit()
    process_waitlist(registration.event)


def process_waitlist(event):
    """Promote the next eligible waitlisted student when a seat is available.
    
    Uses the EventWaitlist model to find the next student in position order,
    creates a confirmed Registration for them, and renumbers remaining waitlist
    positions. Returns the new Registration or None if no one is promoted.
    """
    from app import EventWaitlist, Registration, Ticket

    if available_seats(event) <= 0:
        return None
    waiting = EventWaitlist.query.filter_by(
        event_id=event.id, status="waiting"
    ).order_by(EventWaitlist.waitlist_position).first()
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
    
    # Mark this entry as promoted
    waiting.status = "promoted"
    waiting.notified = True
    
    # Renumber remaining waitlist positions
    db.session.query(EventWaitlist).filter(
        EventWaitlist.event_id == event.id,
        EventWaitlist.status == "waiting",
        EventWaitlist.waitlist_position > waiting.waitlist_position,
    ).update(
        {"waitlist_position": EventWaitlist.waitlist_position - 1},
        synchronize_session="fetch",
    )
    
    notify(waiting.user_id, "Waitlist promoted",
           f"A seat is now available for {event.title}. Your position has been promoted to a confirmed registration.",
           "registration", url_for("ticket", registration_id=registration.id),
           event.id)
    audit(None, "waitlist.promoted", "Registration", registration.id,
          f"Waitlist seat promoted for {event.title} at original position {waiting.waitlist_position}.")
    db.session.commit()
    return registration


def add_to_waitlist(event, user):
    """Add a student to the event waitlist.
    
    Returns a tuple ``(waitlist_entry, position)``.
    Raises ValueError if the student cannot join the waitlist.
    """
    from app import EventWaitlist

    # Check if already on waitlist (active)
    existing = EventWaitlist.query.filter_by(
        event_id=event.id, user_id=user.id, status="waiting"
    ).first()
    if existing:
        return existing, existing.waitlist_position

    # Check if already registered (non-cancelled)
    existing_reg = Registration.query.filter_by(
        event_id=event.id, user_id=user.id
    ).filter(Registration.status != "cancelled").first()
    if existing_reg:
        raise ValueError("You are already registered or on the waitlist for this event.")

    # Determine next position
    max_position = db.session.query(
        db.func.max(EventWaitlist.waitlist_position)
    ).filter(
        EventWaitlist.event_id == event.id,
        EventWaitlist.status == "waiting",
    ).scalar()
    position = (max_position or 0) + 1

    entry = EventWaitlist(
        event_id=event.id,
        user_id=user.id,
        waitlist_position=position,
        status="waiting",
        notified=False,
    )
    db.session.add(entry)
    db.session.flush()
    
    notify(user.id, "Added to Waitlist",
           f"You have been added to the waitlist for '{event.title}'. Your position is #{position}. "
           f"We will notify you if a seat becomes available.",
           "waitlist", url_for("student_waitlist_status", event_id=event.id),
           event.id)
    audit(user, "waitlist.joined", "EventWaitlist", entry.id,
          f"Student joined waitlist for {event.title} at position {position}.")
    db.session.commit()
    return entry, position


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
                "event_reminder",
                url_for("event_details", event_id=reminder.event_id),
                reminder.event_id,
            )
        reminder.status = "sent"
        reminder.sent_at = utcnow()
        delivered += 1
    if due:
        db.session.commit()
    return delivered


def send_registration_deadline_reminders():
    """Send registration deadline reminders for events whose deadline is approaching.

    Runs through approved/published events with a registration_deadline within the
    next 48 hours and notifies every confirmed/pending registration that the
    deadline is near.
    """
    from app import Event, Registration

    now = utcnow()
    cutoff = now + timedelta(hours=48)

    events = (
        Event.query
        .filter(Event.status.in_(["approved", "published"]),
                Event.registration_deadline >= now.date(),
                Event.registration_deadline <= cutoff.date())
        .all()
    )
    delivered = 0
    for event in events:
        regs = Registration.query.filter(
            Registration.event_id == event.id,
            Registration.status.in_(["confirmed", "pending"]),
            Registration.status != "cancelled",
        ).all()
        days = (event.registration_deadline - now.date()).days
        time_label = "today" if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
        for reg in regs:
            notify(
                reg.user_id,
                "Registration Deadline",
                f"The registration deadline for '{event.title}' is {time_label} ({event.registration_deadline.strftime('%d %b %Y')}).",
                "registration_deadline",
                url_for("event_details", event_id=event.id),
                event.id,
            )
            delivered += 1
    if events:
        db.session.commit()
    return delivered


def event_history(event):
    from app import EventActivity, EventApprovalHistory

    approvals = EventApprovalHistory.query.filter_by(event_id=event.id).order_by(EventApprovalHistory.created_at.desc()).all()
    activities = EventActivity.query.filter_by(event_id=event.id).order_by(EventActivity.created_at.desc()).all()
    return approvals + activities


def parse_custom_questions(raw):
    """Parse organizer custom questions from JSON or newline-separated labels.
    
    Supports both legacy format (simple list of labels) and new format 
    (list of field objects with type, required, options, validation, etc.)
    """
    import json

    if not raw:
        return []
    if isinstance(raw, list):
        # Already parsed - ensure each item has required fields
        result = []
        for item in raw:
            if isinstance(item, dict):
                # New format - ensure defaults
                field = {
                    "label": clean_text(item.get("label", ""), 180),
                    "field_type": item.get("field_type", "text"),
                    "required": bool(item.get("required", False)),
                    "options_json": item.get("options_json", []),
                    "validation_json": item.get("validation_json", {}),
                    "placeholder": clean_text(item.get("placeholder", ""), 255),
                    "help_text": clean_text(item.get("help_text", ""), 500),
                    "position": item.get("position", 0),
                    "is_active": item.get("is_active", True),
                }
                result.append(field)
            elif isinstance(item, str):
                # Legacy format - just a label
                result.append({
                    "label": clean_text(item, 180),
                    "field_type": "text",
                    "required": False,
                    "options_json": [],
                    "validation_json": {},
                    "placeholder": "",
                    "help_text": "",
                    "position": 0,
                    "is_active": True,
                })
        return result
    try:
        value = json.loads(raw)
        if isinstance(value, list):
            return parse_custom_questions(value)
    except (TypeError, ValueError):
        pass
    return [{"label": clean_text(line, 180), "field_type": "text", "required": False, "options_json": [], "validation_json": {}, "placeholder": "", "help_text": "", "position": 0, "is_active": True} for line in raw.splitlines() if clean_text(line)]


# ==============================
# EVENT CANCELLATION & RESCHEDULING SERVICES
# ==============================

from datetime import datetime as _dt, date as _date


def _times_overlap(start_a, end_a, start_b, end_b):
    """Return True when two [start, end) time ranges overlap."""
    if not all([start_a, end_a, start_b, end_b]):
        return False
    return start_a < end_b and start_b < end_a


def detect_venue_conflict(event_id, check_date, start_time, end_time, venue, exclude_id=None):
    """Detect venue booking conflicts for a proposed date/time/venue.

    Returns a list of conflicting Event objects.
    """
    from app import Event

    if not check_date or not start_time or not end_time or not venue:
        return []
    start = parse_time(start_time)
    end = parse_time(end_time)
    if not start or not end:
        return []

    query = Event.query.filter(
        Event.venue == venue,
        Event.date == check_date,
        Event.status.in_(["approved", "published", "reschedule_requested", "cancelled"]),
    )
    if exclude_id is not None:
        query = query.filter(Event.id != exclude_id)

    conflicts = []
    for existing in query.all():
        ex_start = parse_time(existing.start_time)
        ex_end = parse_time(existing.end_time)
        if _times_overlap(start, end, ex_start, ex_end):
            conflicts.append(existing)
    return conflicts


def detect_organizer_conflict(organizer_id, check_date, start_time, end_time, exclude_id=None):
    """Detect scheduling conflicts where the same organizer is booked at the proposed time.

    Returns a list of conflicting Event objects.
    """
    from app import Event

    if not organizer_id or not check_date or not start_time or not end_time:
        return []
    start = parse_time(start_time)
    end = parse_time(end_time)
    if not start or not end:
        return []

    query = Event.query.filter(
        Event.organizer_id == organizer_id,
        Event.date == check_date,
        Event.status.in_(["approved", "published", "reschedule_requested", "cancelled"]),
    )
    if exclude_id is not None:
        query = query.filter(Event.id != exclude_id)

    conflicts = []
    for existing in query.all():
        ex_start = parse_time(existing.start_time)
        ex_end = parse_time(existing.end_time)
        if _times_overlap(start, end, ex_start, ex_end):
            conflicts.append(existing)
    return conflicts


def detect_resource_conflict(event_id, check_date, start_time, end_time, venue, exclude_id=None):
    """Detect resource conflicts (venue, organizer, and shared equipment).

    This is the umbrella conflict check that combines venue and organizer
    conflict detection. Returns a dict with ``venue`` and ``organizer`` lists.
    """
    from app import Event

    event = Event.query.get(event_id)
    if event is None:
        return {"venue": [], "organizer": []}

    venue_conflicts = detect_venue_conflict(event_id, check_date, start_time, end_time, venue, exclude_id)
    organizer_conflicts = detect_organizer_conflict(event.organizer_id, check_date, start_time, end_time, exclude_id)

    return {
        "venue": [v for v in venue_conflicts if v.id != event_id],
        "organizer": [o for o in organizer_conflicts if o.id != event_id],
    }


def validate_capacity(venue_name, capacity, existing_registration_count):
    """Validate that a venue's capacity can accommodate existing registrations.

    Returns ``(is_valid, message)``.
    """
    if not capacity or capacity <= 0:
        return False, "Capacity must be a positive number."
    if existing_registration_count and capacity < existing_registration_count:
        return False, (
            f"The new capacity ({capacity}) is less than the number of "
            f"registered students ({existing_registration_count}). "
            f"Either choose a larger venue or reduce capacity."
        )
    return True, ""


def run_all_conflict_checks(event, new_date, new_start_time, new_end_time, new_venue, new_capacity):
    """Run all automatic conflict checks and return a results dict.

    Each check returns a dict with ``passed`` (bool) and ``message`` (str) or
    ``conflicts`` (list of Event objects).
    """
    from app import Event

    active_reg_count = (
        db.session.query(db.func.count(Registration.id))
        .filter(Registration.event_id == event.id, Registration.status != "cancelled")
        .scalar()
        if event else 0
    )

    results = {
        "venue_conflict": {"passed": True, "conflicts": []},
        "organizer_conflict": {"passed": True, "conflicts": []},
        "resource_conflict": {"passed": True, "conflicts": []},
        "capacity": {"passed": True, "message": ""},
    }

    # Venue conflict
    venue_conflicts = detect_venue_conflict(
        event.id, new_date, new_start_time, new_end_time, new_venue
    )
    results["venue_conflict"] = {
        "passed": len(venue_conflicts) == 0,
        "conflicts": venue_conflicts,
        "message": (
            f"Venue conflict: {new_venue} is already booked at the proposed time."
            if venue_conflicts
            else ""
        ),
    }

    # Organizer conflict
    organizer_conflicts = detect_organizer_conflict(
        event.organizer_id, new_date, new_start_time, new_end_time
    )
    results["organizer_conflict"] = {
        "passed": len(organizer_conflicts) == 0,
        "conflicts": organizer_conflicts,
        "message": (
            f"Organizer conflict: you have another event at the proposed time "
            f"({', '.join(c.title for c in organizer_conflicts)})."
            if organizer_conflicts
            else ""
        ),
    }

    # Resource conflict (umbrella)
    resource = detect_resource_conflict(
        event.id, new_date, new_start_time, new_end_time, new_venue, exclude_id=event.id
    )
    results["resource_conflict"] = {
        "passed": len(resource["venue"]) == 0 and len(resource["organizer"]) == 0,
        "conflicts": resource["venue"] + resource["organizer"],
        "message": "",
    }
    if not results["resource_conflict"]["passed"]:
        results["resource_conflict"]["message"] = "Resource conflicts detected."

    # Capacity validation
    cap_valid, cap_msg = validate_capacity(new_venue, new_capacity, active_reg_count)
    results["capacity"] = {
        "passed": cap_valid,
        "message": cap_msg,
    }

    return results


def workflow_status(event):
    """Return the user-facing workflow status label for an event.

    Reflects the full lifecycle:
    Scheduled → Reschedule Requested → Rescheduled →
    Cancellation Requested → Cancelled → Completed
    """
    status = (event.status or "draft").lower()

    if status == "cancelled":
        return "Cancelled"
    if status == "cancellation_requested":
        return "Cancellation Requested"
    if status == "reschedule_requested":
        return "Reschedule Requested"
    if status == "completed":
        return "Completed"

    # Approved / published events
    if status in ("approved", "published"):
        if (event.change_status or "") == "rescheduled":
            return "Rescheduled"
        # Show Completed if the event date has passed and not yet marked completed
        if event.date and event.date < utcnow().date():
            return "Completed"
        return "Scheduled"

    # Fallback for other statuses (draft, pending, etc.)
    return status.replace("_", " ").title()


def _record_status_history(event, new_status, previous_status, actor, reason=""):
    """Record an immutable status-transition row for audit purposes."""
    from app import EventStatusHistory

    row = EventStatusHistory(
        event_id=event.id,
        status=new_status,
        previous_status=previous_status,
        actor_id=actor.id if actor and hasattr(actor, "id") else None,
        change_reason=clean_text(reason, 2000),
    )
    db.session.add(row)
    return row


def _record_activity(event, actor, action, description, metadata=None):
    """Record an event-level activity log entry."""
    from app import EventActivity

    row = EventActivity(
        event_id=event.id,
        actor_id=actor.id if actor and hasattr(actor, "id") else None,
        action=clean_text(action, 80),
        description=clean_text(description, 4000),
        metadata_json=metadata or {},
    )
    db.session.add(row)
    return row


# ==============================
# EVENT LIFECYCLE STATE MACHINE
# ==============================

# Valid event status transitions.  Each key maps a *from* status to a set of
# allowed *target* statuses.  A ``None`` key represents the implicit initial
# (no status set) state, i.e. a brand-new event.
EVENT_STATE_TRANSITIONS = {
    None: {"draft"},
    "draft": {"submitted", "pending"},
    "submitted": {"pending", "changes_requested", "approved", "published", "rejected"},
    "pending": {"changes_requested", "approved", "published", "rejected"},
    "changes_requested": {"submitted", "pending", "approved", "published", "rejected"},
    "approved": {"published", "cancelled", "cancellation_requested", "reschedule_requested", "completed"},
    "published": {"cancelled", "cancellation_requested", "reschedule_requested", "completed"},
    "cancelled": {"approved", "published"},          # un-cancel (rare, admin-only)
    "cancelled": {"approved", "published"},
    "cancellation_requested": {"cancelled", "approved", "published"},
    "reschedule_requested": {"rescheduled", "approved", "published"},
    "rescheduled": {"approved", "published", "cancelled", "cancellation_requested"},
    "rejected": {"draft", "submitted", "pending"},   # can re-submit after rejection
    "completed": {"cancelled", "archived"},
    "archived": set(),                               # terminal state
}


def validate_event_status_transition(current_status, target_status):
    """Validate whether an event status transition is allowed.
    
    Args:
        current_status: The current event status string (or None for new events).
        target_status: The desired new status string.
    
    Returns:
        A tuple ``(is_valid: bool, error_message: str)``.
        ``error_message`` is empty when the transition is valid.
    """
    current = (current_status or "").lower().strip()
    target = (target_status or "").lower().strip()
    
    # Normalise common aliases
    if current == "":
        current = None
    
    # No-op if target equals current
    if current == target:
        return True, ""
    
    allowed = EVENT_STATE_TRANSITIONS.get(current, set())
    if target in allowed:
        return True, ""
    
    return False, (
        f"Cannot transition event status from '{current}' to '{target}'. "
        f"Allowed targets: {', '.join(sorted(allowed)) if allowed else 'none (terminal state)'}"
    )


def can_transition_to(current_status, target_status):
    """Check if an event can transition from one status to another."""
    is_valid, _ = validate_event_status_transition(current_status, target_status)
    return is_valid


def apply_event_status_transition(event, target_status, actor, reason="", commit=True):
    """Apply a status transition to an event with validation.
    
    Records the transition in EventStatusHistory and EventActivity.
    Raises ValueError if the transition is not allowed.
    
    Returns the updated event object.
    """
    current = (event.status or "").lower().strip()
    is_valid, error_msg = validate_event_status_transition(current, target_status)
    if not is_valid:
        raise ValueError(error_msg)
    
    previous = event.status
    event.status = target_status.lower()
    event.updated_at = utcnow()
    
    _record_status_history(event, target_status.lower(), previous, actor, reason)
    _record_activity(
        event, actor, f"event.status.{target_status.lower()}",
        f"{actor.name if actor else 'System'} changed event status from '{previous}' to '{target_status}'. {reason}".strip("."),
        {"from": previous, "to": target_status.lower(), "reason": reason} if reason else {"from": previous, "to": target_status.lower()},
    )
    audit(
        actor, f"event.status.changed", "Event", event.id,
        f"Status changed from '{previous}' to '{target_status}'."
    )
    
    if commit:
        db.session.commit()
    return event


def _notify_registrations(event, title, message, category="event"):
    """Send an in-app notification to every active registered user."""
    regs = Registration.query.filter(
        Registration.event_id == event.id,
        Registration.status != "cancelled",
    ).all()
    for reg in regs:
        notify(reg.user_id, title, message, category)


def request_event_cancellation(event, reason, actor):
    """Organizer requests cancellation of an approved event.

    Sets the event to ``cancellation_requested`` status so that an admin can
    review and approve or reject the request.
    """
    if event.status not in ("approved", "published"):
        raise ValueError("Only approved events can be cancelled.")

    previous = event.status
    event.status = "cancellation_requested"
    event.cancellation_reason = clean_text(reason, 2000)
    event.cancellation_requested_at = utcnow()
    event.cancellation_requested_by = actor.id
    event.updated_at = utcnow()

    _record_status_history(event, "cancellation_requested", previous, actor, reason)
    _record_activity(
        event, actor, "cancellation.requested",
        f"{actor.name} requested cancellation of '{event.title}'. Reason: {reason}",
        {"reason": reason, "requested_by": actor.id},
    )
    audit(actor, "event.cancellation.requested", "Event", event.id,
          f"{actor.name} requested cancellation of {event.title}.")

    # Notify admins
    from app import User
    admins = User.query.filter_by(role="admin").all()
    for admin in admins:
        notify(
            admin.id,
            "Cancellation Request",
            f"Organizer {actor.name} requested cancellation of '{event.title}'. "
            f"Reason: {reason}. Review in the admin cancellation management panel.",
            "event",
            url_for("admin_manage_cancellation", event_id=event.id),
        )

    db.session.commit()
    return event


def approve_event_cancellation(event, actor, notify_students=True):
    """Admin approves a cancellation request.

    - Sets status to ``cancelled``
    - Cancels all active registrations (preserving their history)
    - Revokes student tickets
    - Notifies registered students
    - Preserves the event record (no deletion)
    """
    from app import Ticket, User, send_email, COLLEGE_NAME

    if event.status != "cancellation_requested":
        raise ValueError("Only events with a pending cancellation request can be approved.")

    admin_notes = ""
    if request is not None:
        try:
            admin_notes = clean_text(request.form.get("admin_notes", ""), 2000)
        except RuntimeError:
            admin_notes = ""

    previous = event.status
    event.status = "cancelled"
    event.cancelled_at = utcnow()
    event.cancelled_by = actor.id
    event.cancellation_admin_notes = admin_notes
    event.updated_at = utcnow()

    _record_status_history(event, "cancelled", previous, actor, "Cancellation approved")
    _record_activity(
        event, actor, "cancellation.approved",
        f"{actor.name} approved cancellation of '{event.title}'.",
        {"approved_by": actor.id, "admin_notes": admin_notes},
    )
    audit(actor, "event.cancellation.approved", "Event", event.id,
          f"{actor.name} approved cancellation of {event.title}.")

    # Cancel all active registrations safely
    active_regs = Registration.query.filter(
        Registration.event_id == event.id,
        Registration.status != "cancelled",
    ).all()
    for reg in active_regs:
        reg.status = "cancelled"
        reg.cancellation_reason = "Event was cancelled by organizer/admin."
        reg.cancelled_at = utcnow()
        if reg.ticket_record:
            reg.ticket_record.status = "revoked"
            reg.ticket_record.revoked_reason = "Event cancelled"
            reg.ticket_record.revoked_at = utcnow()

    # Notify the organizer
    notify(
        event.organizer_id,
        "Event Cancelled",
        f"Your cancellation request for '{event.title}' has been approved. "
        f"All registrations have been cancelled.",
        "event",
        url_for("manage_event", event_id=event.id),
    )

    # Notify registered students
    if notify_students and active_regs:
        college = COLLEGE_NAME
        for reg in active_regs:
            student_message = (
                f"The event '{event.title}' scheduled on "
                f"{event.date.strftime('%d %B %Y') if event.date else 'N/A'} "
                f"({event.start_time} - {event.end_time}) has been cancelled. "
                f"Reason: {event.cancellation_reason or 'Not specified'}"
            )
            notify(
                reg.user_id,
                "Event Cancelled",
                student_message,
                "event",
                url_for("my_registrations"),
            )
            # Attempt email delivery (non-fatal on failure)
            if reg.user.email:
                try:
                    subject = f"EVENT CANCELLED: {event.title}"
                    body = (
                        f"Dear {reg.user.name},\n\n"
                        f"We regret to inform you that the event '{event.title}' has been cancelled.\n\n"
                        f"Event Details:\n"
                        f"  Date: {event.date.strftime('%d %B %Y') if event.date else 'N/A'}\n"
                        f"  Time: {event.start_time} - {event.end_time}\n"
                        f"  Venue: {event.venue}\n\n"
                        f"Reason: {event.cancellation_reason or 'Not specified'}\n\n"
                        f"Your registration has been automatically cancelled and any ticket has been revoked.\n"
                        f"No further action is required on your part.\n\n"
                        f"Thank you,\n{college} — Campus Event Management System"
                    )
                    send_email(reg.user.email, subject, body)
                except Exception:
                    pass

    db.session.commit()
    return event, active_regs


def reject_event_cancellation(event, actor, reason=""):
    """Admin rejects a cancellation request — event returns to approved."""
    if event.status != "cancellation_requested":
        raise ValueError("Only events with a pending cancellation request can be rejected.")

    previous = event.status
    event.status = "approved"
    event.cancellation_reason = None
    event.cancellation_requested_at = None
    event.cancellation_requested_by = None
    event.cancellation_admin_notes = clean_text(reason, 2000)
    event.updated_at = utcnow()

    _record_status_history(event, "approved", previous, actor, reason or "Cancellation rejected")
    _record_activity(
        event, actor, "cancellation.rejected",
        f"{actor.name} rejected cancellation of '{event.title}'. Reason: {reason or 'No reason given'}",
        {"rejection_reason": reason or ""},
    )
    audit(actor, "event.cancellation.rejected", "Event", event.id,
          f"{actor.name} rejected cancellation of {event.title}.")

    notify(
        event.organizer_id,
        "Cancellation Rejected",
        f"Your cancellation request for '{event.title}' was rejected. "
        f"The event remains scheduled. Reason: {reason or 'Not specified'}",
        "event",
        url_for("manage_event", event_id=event.id),
    )

    db.session.commit()
    return event


def request_event_reschedule(event, new_date, new_start_time, new_end_time, new_venue,
                             new_capacity=None, reason="", actor=None):
    """Organizer requests rescheduling of an approved event.

    Stores the proposed new date/time/venue and sets status to
    ``reschedule_requested`` so an admin can approve or reject.

    Automatically runs all conflict checks (venue, organizer, resource, capacity)
    and raises ``ValueError`` with a summary message if any fail.
    """
    if event.status not in ("approved", "published"):
        raise ValueError("Only approved events can be rescheduled.")

    # Validate the proposed values
    if not new_date:
        raise ValueError("A new date is required for rescheduling.")
    if isinstance(new_date, str):
        new_date = parse_date(new_date)
    if new_date is None:
        raise ValueError("Please provide a valid new date.")
    if new_date < utcnow().date():
        raise ValueError("The new event date cannot be in the past.")
    new_start = parse_time(new_start_time)
    new_end = parse_time(new_end_time)
    if not new_start or not new_end:
        raise ValueError("Please provide valid start and end times.")
    if new_end <= new_start:
        raise ValueError("The new end time must be after the new start time.")
    if not new_venue or not new_venue.strip():
        raise ValueError("A new venue is required for rescheduling.")

    new_start_time = new_start_time.strip()
    new_end_time = new_end_time.strip()
    new_venue = new_venue.strip()
    effective_capacity = new_capacity or event.capacity

    # ---- Automatically re-run all conflict checks ----
    conflict_results = run_all_conflict_checks(
        event, new_date, new_start_time, new_end_time, new_venue, effective_capacity
    )
    conflict_messages = []
    for check_name, result in conflict_results.items():
        if not result["passed"]:
            conflict_messages.append(result.get("message") or f"{check_name} check failed")

    if conflict_messages:
        raise ValueError(
            "Automatic conflict detection identified the following issues:\n"
            + "\n".join(f"  - {msg}" for msg in conflict_messages)
        )

    previous = event.status
    event.status = "reschedule_requested"
    event.proposed_date = new_date
    event.proposed_start_time = new_start_time
    event.proposed_end_time = new_end_time
    event.proposed_venue = new_venue
    event.proposed_capacity = effective_capacity
    event.reschedule_reason = clean_text(reason, 2000)
    event.reschedule_requested_at = utcnow()
    event.reschedule_requested_by = actor.id if actor else event.organizer_id
    event.updated_at = utcnow()

    _record_status_history(event, "reschedule_requested", previous, actor, reason)
    _record_activity(
        event, actor, "reschedule.requested",
        f"{actor.name} requested rescheduling of '{event.title}' "
        f"to {new_date} ({new_start_time}-{new_end_time}) at {new_venue}.",
        {
            "proposed_date": new_date.isoformat() if new_date else None,
            "proposed_start_time": new_start_time,
            "proposed_end_time": new_end_time,
            "proposed_venue": new_venue,
            "proposed_capacity": effective_capacity,
            "reason": reason,
        },
    )
    audit(actor, "event.reschedule.requested", "Event", event.id,
          f"{actor.name} requested reschedule of {event.title} to {new_date}.")

    # Notify admins
    from app import User
    admins = User.query.filter_by(role="admin").all()
    for admin in admins:
        notify(
            admin.id,
            "Reschedule Request",
            f"Organizer {actor.name} requested rescheduling of '{event.title}' "
            f"to {new_date.strftime('%d %b %Y') if new_date else 'N/A'}. "
            f"Review in the admin management panel.",
            "event",
            url_for("admin_manage_reschedule", event_id=event.id),
        )

    db.session.commit()
    return event, conflict_results


def approve_event_reschedule(event, actor, notify_students=True):
    """Admin approves a reschedule request.

    - Applies the proposed date/time/venue/capacity
    - Sets status back to ``approved`` and marks ``change_status = "rescheduled"``
    - Preserves original data for history
    - Notifies registered students of the new details
    """
    if event.status != "reschedule_requested":
        raise ValueError("Only events with a pending reschedule request can be approved.")

    # Snapshot the original data before applying changes
    original_snapshot = {
        "date": event.date.isoformat() if event.date else None,
        "start_time": event.start_time,
        "end_time": event.end_time,
        "venue": event.venue,
        "capacity": event.capacity,
        "venue_id": event.venue_id,
        "registration_deadline": (
            event.registration_deadline.isoformat() if event.registration_deadline else None
        ),
    }
    if not event.original_data:
        event.original_data = original_snapshot

    # Apply the proposed values
    event.date = event.proposed_date
    event.start_time = event.proposed_start_time
    event.end_time = event.proposed_end_time
    event.venue = event.proposed_venue
    event.capacity = event.proposed_capacity or event.capacity

    previous = event.status
    event.status = "approved"
    event.change_status = "rescheduled"
    # Clear proposed fields
    event.proposed_date = None
    event.proposed_start_time = None
    event.proposed_end_time = None
    event.proposed_venue = None
    event.proposed_capacity = None
    event.proposed_venue_id = None
    event.reschedule_reason = None
    event.reschedule_requested_at = None
    event.reschedule_requested_by = None
    event.reschedule_admin_notes = ""
    event.updated_at = utcnow()

    _record_status_history(event, "approved", previous, actor, "Reschedule approved")
    _record_activity(
        event, actor, "reschedule.approved",
        f"{actor.name} approved rescheduling of '{event.title}'.",
        {
            "original": original_snapshot,
            "new_date": event.date.isoformat() if event.date else None,
            "new_start_time": event.start_time,
            "new_end_time": event.end_time,
            "new_venue": event.venue,
        },
    )
    audit(actor, "event.reschedule.approved", "Event", event.id,
          f"{actor.name} approved reschedule of {event.title}.")

    # Notify the organizer
    notify(
        event.organizer_id,
        "Reschedule Approved",
        f"Your reschedule request for '{event.title}' has been approved. "
        f"New date: {event.date.strftime('%d %b %Y') if event.date else 'N/A'}, "
        f"Time: {event.start_time} - {event.end_time}, Venue: {event.venue}.",
        "event",
        url_for("manage_event", event_id=event.id),
    )

    # Notify registered students
    if notify_students:
        from app import User, send_email, COLLEGE_NAME
        active_regs = Registration.query.filter(
            Registration.event_id == event.id,
            Registration.status != "cancelled",
        ).all()
        college = COLLEGE_NAME
        for reg in active_regs:
            student_message = (
                f"The event '{event.title}' has been rescheduled.\n\n"
                f"New Details:\n"
                f"  Date: {event.date.strftime('%d %B %Y') if event.date else 'N/A'}\n"
                f"  Time: {event.start_time} - {event.end_time}\n"
                f"  Venue: {event.venue}\n\n"
                f"Previous date: {original_snapshot['date']}\n"
                f"Please update your calendar accordingly."
            )
            notify(
                reg.user_id,
                "Event Rescheduled",
                student_message,
                "event",
                url_for("my_registrations"),
            )
            if reg.user.email:
                try:
                    subject = f"EVENT RESCHEDULED: {event.title}"
                    body = (
                        f"Dear {reg.user.name},\n\n"
                        f"The event '{event.title}' has been rescheduled. Please note the new details:\n\n"
                        f"New Details:\n"
                        f"  Date: {event.date.strftime('%d %B %Y') if event.date else 'N/A'}\n"
                        f"  Time: {event.start_time} - {event.end_time}\n"
                        f"  Venue: {event.venue}\n\n"
                        f"Previous Details:\n"
                        f"  Date: {original_snapshot.get('date', 'N/A')}\n"
                        f"  Time: {original_snapshot.get('start_time', 'N/A')} - {original_snapshot.get('end_time', 'N/A')}\n"
                        f"  Venue: {original_snapshot.get('venue', 'N/A')}\n\n"
                        f"Your registration remains active. No action is required.\n\n"
                        f"Thank you,\n{college} — Campus Event Management System"
                    )
                    send_email(reg.user.email, subject, body)
                except Exception:
                    pass

    db.session.commit()
    return event


def reject_event_reschedule(event, actor, reason=""):
    """Admin rejects a reschedule request — event returns to approved."""
    if event.status != "reschedule_requested":
        raise ValueError("Only events with a pending reschedule request can be rejected.")

    previous = event.status
    event.status = "approved"
    event.reschedule_admin_notes = clean_text(reason, 2000)
    # Clear proposed fields
    event.proposed_date = None
    event.proposed_start_time = None
    event.proposed_end_time = None
    event.proposed_venue = None
    event.proposed_capacity = None
    event.proposed_venue_id = None
    event.reschedule_reason = None
    event.reschedule_requested_at = None
    event.reschedule_requested_by = None
    event.updated_at = utcnow()

    _record_status_history(event, "approved", previous, actor, reason or "Reschedule rejected")
    _record_activity(
        event, actor, "reschedule.rejected",
        f"{actor.name} rejected reschedule of '{event.title}'. Reason: {reason or 'No reason given'}",
        {"rejection_reason": reason or ""},
    )
    audit(actor, "event.reschedule.rejected", "Event", event.id,
          f"{actor.name} rejected reschedule of {event.title}.")

    notify(
        event.organizer_id,
        "Reschedule Rejected",
        f"Your reschedule request for '{event.title}' was rejected. "
        f"The event remains scheduled at the original time. "
        f"Reason: {reason or 'Not specified'}",
        "event",
        url_for("manage_event", event_id=event.id),
    )

    db.session.commit()
    return event


# ==============================
# FEEDBACK FORM (GENERATION) SERVICES
# ==============================

FEEDBACK_QUESTION_TYPES = [
    ("rating_stars", "Star Rating (1-5)"),
    ("rating_number", "Numeric Rating"),
    ("text", "Short Text"),
    ("textarea", "Long Text"),
    ("select", "Dropdown / Select"),
    ("radio", "Multiple Choice (Radio)"),
    ("checkbox", "Checkboxes"),
    ("nps", "Net Promoter Score (0-10)"),
]


def parse_feedback_questions(raw):
    """Parse a JSON list of feedback-question objects into normalised dicts.

    Accepts either a JSON string or a native Python list.  Each item may be a
    dict with the full question schema or a legacy plain label string.
    """
    import json

    if not raw:
        return []
    if isinstance(raw, list):
        result = []
        for item in raw:
            if isinstance(item, dict):
                result.append({
                    "label": clean_text(item.get("label", ""), 300),
                    "question_type": item.get("question_type", "rating_stars"),
                    "required": bool(item.get("required", False)),
                    "options_json": item.get("options_json", []) if isinstance(item.get("options_json"), list) else [],
                    "rating_scale": int(item.get("rating_scale", 5) or 5),
                    "position": int(item.get("position", 0) or 0),
                    "is_active": item.get("is_active", True),
                })
            elif isinstance(item, str) and clean_text(item):
                result.append({
                    "label": clean_text(item, 300),
                    "question_type": "rating_stars",
                    "required": False,
                    "options_json": [],
                    "rating_scale": 5,
                    "position": len(result),
                    "is_active": True,
                })
        return result
    try:
        value = json.loads(raw)
        if isinstance(value, list):
            return parse_feedback_questions(value)
    except (TypeError, ValueError):
        pass
    return []


def get_active_feedback_template(event_id):
    """Return the active :class:`FeedbackFormTemplate` for *event_id*, or ``None``."""
    from app import FeedbackFormTemplate

    return FeedbackFormTemplate.query.filter_by(
        event_id=event_id, is_active=True
    ).order_by(FeedbackFormTemplate.updated_at.desc()).first()


def create_feedback_form_template(event, title, description, questions_data, organizer):
    """Create a new ``FeedbackFormTemplate`` with its questions for *event*."""
    from app import FeedbackFormTemplate, FeedbackFormQuestion

    template = FeedbackFormTemplate(
        event_id=event.id,
        title=clean_text(title, 180) or "Event Feedback Form",
        description=clean_text(description, 2000) if description else None,
        is_active=True,
        created_by=organizer.id if organizer else None,
    )
    db.session.add(template)
    db.session.flush()  # obtain template.id before creating questions

    questions = parse_feedback_questions(questions_data) or []
    if not questions:
        questions = [{
            "label": "Overall Rating",
            "question_type": "rating_stars",
            "required": True,
            "options_json": [],
            "rating_scale": 5,
            "position": 0,
            "is_active": True,
        }]

    for idx, q in enumerate(questions):
        db.session.add(FeedbackFormQuestion(
            template_id=template.id,
            label=q["label"],
            question_type=q["question_type"],
            required=q["required"],
            options_json=q["options_json"],
            rating_scale=q["rating_scale"],
            position=idx,
            is_active=q.get("is_active", True),
        ))

    audit(organizer, "feedback_form.created", "FeedbackFormTemplate", template.id,
          f"{organizer.name} created feedback form '{title}' for {event.title}.")
    if organizer and organizer.id == event.organizer_id:
        notify(
            event.organizer_id,
            "Feedback Form Created",
            f"A custom feedback form has been created for '{event.title}'.",
            "feedback",
            action_url=url_for("organizer_feedback_forms"),
            event_id=event.id,
        )
    db.session.commit()
    return template


def update_feedback_form_template(template, title, description, questions_data):
    """Overwrite the title/description and replace all questions on *template*."""
    from app import FeedbackFormQuestion

    template.title = clean_text(title, 180) or template.title
    template.description = clean_text(description, 2000) if description else None
    template.updated_at = utcnow()

    # Replace existing questions
    FeedbackFormQuestion.query.filter_by(template_id=template.id).delete()
    db.session.flush()

    questions = parse_feedback_questions(questions_data) or []
    if not questions:
        questions = [{
            "label": "Overall Rating",
            "question_type": "rating_stars",
            "required": True,
            "options_json": [],
            "rating_scale": 5,
            "position": 0,
            "is_active": True,
        }]

    for idx, q in enumerate(questions):
        db.session.add(FeedbackFormQuestion(
            template_id=template.id,
            label=q["label"],
            question_type=q["question_type"],
            required=q["required"],
            options_json=q["options_json"],
            rating_scale=q["rating_scale"],
            position=idx,
            is_active=q.get("is_active", True),
        ))

    db.session.commit()
    db.session.refresh(template)
    return template


def submit_feedback_form(registration, template, answers_data, is_anonymous=False):
    """Record a student's submission of a custom feedback form atomically.

    *answers_data* maps ``question_id`` (as a string) -> answer value (string).
    Returns the created ``FeedbackFormResponse``.
    Raises ``ValueError`` if the student already responded.
    """
    from app import FeedbackFormResponse, FeedbackFormAnswer

    existing = FeedbackFormResponse.query.filter_by(registration_id=registration.id).first()
    if existing:
        raise ValueError("You have already submitted feedback for this event.")

    response = FeedbackFormResponse(
        registration_id=registration.id,
        template_id=template.id,
        is_anonymous=bool(is_anonymous),
    )
    db.session.add(response)
    db.session.flush()  # obtain response.id

    for q in template.questions:
        if not q.is_active:
            continue
        key = str(q.id)
        value = answers_data.get(key)
        if not value and q.required:
            db.session.rollback()
            raise ValueError(f"The question '{q.label}' is required.")
        if value is not None:
            db.session.add(FeedbackFormAnswer(
                response_id=response.id,
                question_id=q.id,
                value=str(value).strip() if isinstance(value, str) else str(value),
            ))

    # Notify the organiser
    notify(
        registration.event.organizer_id,
        "Feedback Received",
        f"New feedback form response received for '{registration.event.title}'.",
        "feedback",
        action_url=url_for("organizer_feedback_form_responses", form_id=template.id),
        event_id=registration.event_id,
    )
    audit(registration.user, "feedback_form.submitted", "FeedbackFormResponse", response.id,
          f"Feedback submitted for {registration.event.title} via custom form.")
    db.session.commit()
    return response


def feedback_form_stats(event_id):
    """Compute analytics for the active feedback form of *event_id*.

    Returns a dict with counts, per-question response breakdowns, and averages.
    Returns ``{"has_custom_form": False}`` when no active form exists.
    """
    from app import FeedbackFormTemplate, FeedbackFormQuestion, FeedbackFormResponse, FeedbackFormAnswer, Registration

    template = get_active_feedback_template(event_id)
    if not template:
        return {"has_custom_form": False}

    regs = Registration.query.filter_by(event_id=event_id).all()
    total_regs = len(regs)
    total_responses = FeedbackFormResponse.query.filter_by(template_id=template.id).count()
    response_rate = round(total_responses / total_regs * 100, 1) if total_regs else 0

    questions_data = []
    for q in template.questions:
        if not q.is_active:
            continue
        answers = FeedbackFormAnswer.query.join(
            FeedbackFormResponse, FeedbackFormAnswer.response_id == FeedbackFormResponse.id
        ).filter(
            FeedbackFormResponse.template_id == template.id,
            FeedbackFormAnswer.question_id == q.id,
        ).all()

        values = [a.value for a in answers if a.value is not None]
        rating_values = []
        for v in values:
            try:
                rating_values.append(int(v))
            except (ValueError, TypeError):
                pass

        avg = round(sum(rating_values) / len(rating_values), 2) if rating_values else 0

        distribution = {}
        if q.question_type in ("rating_stars", "rating_number", "nps"):
            max_val = q.rating_scale if q.question_type != "nps" else 10
            for i in range(1, max_val + 1):
                distribution[str(i)] = sum(1 for v in rating_values if v == i)
        else:
            distribution = dict(Counter(values)) if values else {}

        questions_data.append({
            "id": q.id,
            "label": q.label,
            "question_type": q.question_type,
            "required": q.required,
            "response_count": len(values),
            "average": avg,
            "distribution": distribution,
        })

    return {
        "has_custom_form": True,
        "template": template.to_dict(),
        "total_registrations": total_regs,
        "total_responses": total_responses,
        "response_rate": response_rate,
        "questions": questions_data,
    }


# ==============================
# STUDENT EVENT FEEDBACK SERVICES
# ==============================

FEEDBACK_ELIGIBILITY_CHOICES = [
    {"value": "attendees", "label": "Event Attendees"},
    {"value": "registrants", "label": "All Registrants"},
    {"value": "paid_registrants", "label": "Paid Registrants Only"},
]

# Registrations whose status counts as a valid, confirmed participant.
CONFIRMED_REGISTRATION_STATUSES = ("confirmed", "approved")
# Payment statuses that satisfy the "paid_registrants" eligibility rule.
PAID_PAYMENT_STATUSES = ("paid", "successful", "completed")


def is_event_eligible_for_feedback(event):
    """Return True if feedback collection is enabled for *event*.

    Feedback is enabled when the organiser has not explicitly disabled it
    (``feedback_enabled`` defaults to ``True``).  When the organiser has
    attached an active *custom* feedback form the static star-rating form is
    also considered available, but callers may decide to prefer the custom
    form instead.
    """
    if not getattr(event, "feedback_enabled", True):
        return False
    return True


def is_eligible_for_feedback(registration):
    """Determine whether *registration* may submit a static feedback entry.

    Returns a ``(eligible: bool, reason: str)`` tuple.  ``eligible`` is
    ``True`` when every configured business rule is satisfied:

    * The event has not disabled feedback collection.
    * The event date has passed (event is completed/past).
    * The registration status meets the configured eligibility policy
      (``attendees``, ``registrants``, or ``paid_registrants``).
    * The feedback deadline (if configured) has not passed.

    The check is intentionally independent of the faculty "completed" status
    so that feedback becomes available automatically once the event date
    elapses.
    """
    from app import Feedback

    event = registration.event

    # 1. Global enable flag
    if not is_event_eligible_for_feedback(event):
        return False, "Feedback is not enabled for this event."

    # 2. Event must have concluded
    if not (event.date and event.date < utcnow().date()):
        return False, "Feedback is only available after the event has completed."

    # 3. Registration status must be confirmed/approved
    if registration.status not in CONFIRMED_REGISTRATION_STATUSES:
        return False, "Only confirmed registrants can submit feedback."

    # 4. Apply the configured eligibility policy
    policy = (event.feedback_eligibility or "attendees").lower()
    if policy == "paid_registrants":
        if registration.payment_status not in PAID_PAYMENT_STATUSES:
            return False, "Feedback is only available for paid registrants."
    elif policy == "registrants":
        # Any confirmed registrant — already checked above
        pass
    elif policy == "attendees":
        if not registration.attended:
            return False, "Feedback is only available for students who attended the event."

    # 5. Optional deadline after event completion
    deadline_days = getattr(event, "feedback_deadline_days", None) or None
    if deadline_days is not None:
        deadline = event.date + timedelta(days=deadline_days)
        if utcnow().date() > deadline:
            return False, "The feedback submission deadline for this event has passed."

    return True, ""


def submit_student_feedback(registration, rating, comment="", is_anonymous=False,
                            theme=None, organization_rating=None, venue_rating=None,
                            speaker_rating=None, registration_experience_rating=None):
    """Record or update a student's static (star-rating) feedback entry.

    *rating* is clamped to the 1–5 range.  Category ratings are likewise
    clamped.  ``theme`` is truncated to 255 characters.

    Duplicate prevention follows the configured update policy:
    if an existing ``Feedback`` row is found and the event's
    ``feedback_allow_updates`` flag is ``False`` (the default), a
    ``ValueError`` is raised.  When updates *are* allowed the existing row is
    updated in place.

    Returns the resulting ``Feedback`` instance.
    Raises ``ValueError`` when the student is ineligible or when duplicate
    submission is blocked.
    """
    from app import Feedback

    eligible, reason = is_eligible_for_feedback(registration)
    if not eligible:
        raise ValueError(reason)

    # Clamp and normalise inputs
    rating = _clamp_int(rating, 1, 5, default=5)
    organization_rating = _clamp_int(organization_rating, 1, 5)
    venue_rating = _clamp_int(venue_rating, 1, 5)
    speaker_rating = _clamp_int(speaker_rating, 1, 5)
    registration_experience_rating = _clamp_int(registration_experience_rating, 1, 5)
    comment = clean_text(comment or "", 10000)
    theme = clean_text(theme or "", 255) or None

    event = registration.event

    existing = Feedback.query.filter_by(registration_id=registration.id).first()
    if existing:
        if not getattr(event, "feedback_allow_updates", False):
            raise ValueError("You have already submitted feedback for this event.")
        existing.rating = rating
        existing.organization_rating = organization_rating
        existing.venue_rating = venue_rating
        existing.speaker_rating = speaker_rating
        existing.registration_experience_rating = registration_experience_rating
        existing.comment = comment
        existing.is_anonymous = bool(is_anonymous)
        existing.theme = theme
        existing.created_at = utcnow()
        feedback_obj = existing
        action_desc = "updated"
    else:
        feedback_obj = Feedback(
            registration_id=registration.id,
            rating=rating,
            organization_rating=organization_rating,
            venue_rating=venue_rating,
            speaker_rating=speaker_rating,
            registration_experience_rating=registration_experience_rating,
            comment=comment,
            is_anonymous=bool(is_anonymous),
            theme=theme,
        )
        db.session.add(feedback_obj)
        db.session.flush()
        action_desc = "submitted"

    # Notify organiser (do not leak anonymously flag to the student notification)
    notify(
        registration.event.organizer_id,
        "New Feedback Received",
        f"A student rated '{event.title}' — see the feedback dashboard for details.",
        "feedback_reminder",
        action_url=url_for("organizer_event_feedback", event_id=event.id),
        event_id=event.id,
    )

    audit(
        registration.user,
        "feedback.submitted",
        "Feedback",
        feedback_obj.id,
        f"Feedback {action_desc} for {event.title}.",
    )
    db.session.commit()
    return feedback_obj


def _clamp_int(value, low, high, default=None):
    """Coerce *value* to an int clamped to ``[low, high]``.

    Returns ``default`` when *value* is falsy / not coercible.
    """
    if value is None or value == "":
        return default
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default

