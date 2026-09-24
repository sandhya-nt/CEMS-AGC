# Script to insert new routes into app.py
with open('app.py', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

marker = 'return render_template("student/register_event.html", event=event, terms_required=True)'
pos = content.find(marker)
end_of_line = content.find('\n', pos)

# Find the position right after the blank line (two newlines)
insert_pos = content.find('\n\n@app.route("/student/registrations")', end_of_line)

new_routes = '''

@app.route("/student/events")
@role_required("student")
def student_events():
    """Student-focused events listing with registration capability."""
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    status = request.args.get("status", "open").strip()
    page = request.args.get("page", 1, type=int)
    today = datetime.utcnow().date()

    query = Event.query.filter(Event.status.in_(["approved", "published"]))
    if q:
        query = query.filter(Event.title.ilike(f"%{q}%"))
    if category:
        query = query.filter_by(category=category)

    query = query.filter(Event.date >= today)

    if status == "open":
        query = query.filter(Event.registration_deadline >= today)
    elif status == "full":
        subq = db.session.query(
            Registration.event_id,
            db.func.count(Registration.id).label("registered")
        ).filter(
            Registration.status.in_(["confirmed", "pending", "approved"])
        ).group_by(Registration.event_id).subquery()
        query = query.join(subq, Event.id == subq.c.event_id).filter(subq.c.registered >= Event.capacity)

    pagination = query.order_by(Event.date.asc()).paginate(page=page, per_page=12, error_out=False)
    categories = [r[0] for r in db.session.query(Event.category).distinct().all()]

    event_data = []
    for event in pagination.items:
        registered_count = Registration.query.filter(
            Registration.event_id == event.id,
            Registration.status.in_(["confirmed", "pending", "approved"]),
        ).count()
        is_registered = Registration.query.filter(
            Registration.user_id == current_user.id,
            Registration.event_id == event.id,
            Registration.status != "cancelled",
        ).first() is not None
        reg_deadline_passed = event.registration_deadline and event.registration_deadline < today

        event_data.append({
            "event": event,
            "registered_count": registered_count,
            "is_registered": is_registered,
            "registration_open": (
                event.status in ("approved", "published")
                and not is_registered
                and registered_count < event.capacity
                and not reg_deadline_passed
                and event.date >= today
            ),
            "seats_available": max(0, event.capacity - registered_count),
        })

    return render_template(
        "student/events.html",
        events=event_data,
        categories=categories,
        q=q,
        category=category,
        status=status,
        pagination=pagination,
    )


@app.route("/api/events/<int:event_id>/validate-registration", methods=["GET"])
@role_required("student")
def api_validate_registration(event_id):
    """Pre-registration validation endpoint with explicit check results."""
    event = Event.query.get_or_404(event_id)
    today = datetime.utcnow().date()
    checks = {}

    checks["authentication"] = {
        "passed": current_user.is_authenticated and current_user.role == "student",
        "message": "Authenticated as student." if current_user.is_authenticated else "Authentication required.",
    }

    checks["eligibility"] = {
        "passed": event.status in ("approved", "published"),
        "message": "Event is open for registration." if event.status in ("approved", "published") else f"Event status is '{event.status}' — not eligible for registration.",
    }

    deadline = event.registration_deadline
    deadline_passed = deadline is not None and today > deadline
    checks["deadline"] = {
        "passed": not deadline_passed,
        "message": f"Registration deadline is {deadline.strftime('%d %b %Y')}." if deadline else "No registration deadline — open.",
    }

    registered_count = Registration.query.filter(
        Registration.event_id == event.id,
        Registration.status.in_(["confirmed", "pending", "approved"]),
    ).count()
    capacity_available = registered_count < event.capacity
    checks["capacity"] = {
        "passed": capacity_available,
        "message": f"{event.capacity - registered_count} seats available (of {event.capacity})." if capacity_available else "Event is at full capacity.",
        "registered": registered_count,
        "capacity": event.capacity,
    }

    existing = Registration.query.filter(
        Registration.user_id == current_user.id,
        Registration.event_id == event.id,
        Registration.status != "cancelled",
    ).first()
    checks["duplicate"] = {
        "passed": existing is None,
        "message": "Not yet registered — eligible to register." if existing is None else "You are already registered for this event.",
    }

    checks["event_status"] = {
        "passed": event.status not in ("rejected", "cancelled"),
        "message": "Event is active." if event.status not in ("rejected", "cancelled") else f"Event is {event.status}.",
    }

    event_past = event.date is not None and event.date < today
    checks["event_date"] = {
        "passed": not event_past,
        "message": "Event is upcoming." if not event_past else "Event date has already passed.",
    }

    all_passed = all(c["passed"] for c in checks.values())
    return jsonify({
        "success": all_passed,
        "eligible": all_passed,
        "checks": checks,
        "event_id": event.id,
        "event_title": event.title,
        "registered_count": registered_count,
        "capacity": event.capacity,
    })


@app.route("/registration/result/<int:registration_id>")
@login_required
def registration_result(registration_id):
    """Show registration success or error result page."""
    reg = Registration.query.get_or_404(registration_id)
    if reg.user_id != current_user.id and current_user.role not in ("admin", "organizer"):
        abort(403)

    event = reg.event
    today = datetime.utcnow().date()

    is_successful = reg.status in ("confirmed", "approved", "pending")
    reg_deadline_passed = event.registration_deadline and event.registration_deadline < today
    event_rejected = event.status == "rejected"
    event_cancelled = event.status == "cancelled"
    event_past = event.date is not None and event.date < today

    failed_reason = ""
    if event_rejected:
        failed_reason = "This event has been rejected and cannot accept registrations."
    elif event_cancelled:
        failed_reason = "This event has been cancelled."
    elif event_past:
        failed_reason = "This event has already taken place."
    elif reg_deadline_passed:
        failed_reason = "Registration deadline has passed for this event."

    return render_template(
        "student/registration_result.html",
        success=is_successful and not reg_deadline_passed and not event_rejected and not event_cancelled and not event_past,
        status_label="Confirmed" if is_successful and not reg_deadline_passed and not event_rejected and not event_cancelled and not event_past else "Failed",
        event_title=event.title,
        event_date=event.date.strftime('%d %B %Y') if event.date else "—",
        event_venue=event.venue,
        ticket_code=reg.ticket_code,
        registration_id=reg.id,
        reg_status=reg.status,
        registered_at=reg.registered_at.strftime('%d %b %Y %H:%M') if reg.registered_at else "—",
        error_reason=failed_reason,
        error_icon="🚫",
        error_title="Registration Failed",
        error_description="Your registration could not be completed due to eligibility issues.",
        event_id=event.id,
    )

'''

# Insert the new routes
new_content = content[:insert_pos] + new_routes + content[insert_pos:]

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Routes inserted successfully!")
print(f"New file size: {len(new_content)} chars (was {len(content)})")
