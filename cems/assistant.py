"""CampusAssistantService - AI-Powered Campus Event Assistant service layer.

This module provides a service layer that retrieves relevant database
information based on the current user's role and the user's query intent.
The retrieved data is then passed to the AI layer for natural language
response generation.

Key principle: The AI NEVER directly executes SQL. All data retrieval
goes through this service layer using safe ORM queries.
"""

import os
from datetime import datetime, timedelta

from .extensions import db


class CampusAssistantService:
    """Service layer for the AI Campus Event Assistant.

    Retrieves relevant database information based on user role and
    query intent, then provides structured data to the AI bridge.
    Never allows direct SQL execution.
    """

    # Roles that can use the assistant
    ASSISTANT_ROLES = {"student", "organizer", "admin", "teacher", "volunteer"}

    def __init__(self, current_user, db_session):
        """Initialize with the current authenticated user and DB session.

        Args:
            current_user: The Flask-Login current_user object.
            db_session: SQLAlchemy session (use db.session from extensions).
        """
        self.current_user = current_user
        self.db = db_session
        self.user_id = current_user.id if current_user.is_authenticated else None
        self.user_role = current_user.role if current_user.is_authenticated else None

    def is_authorized(self):
        """Check if the current user is authorized to use the assistant."""
        return self.user_role in self.ASSISTANT_ROLES and self.user_id is not None

    def _is_organizer_of_event(self, event_id):
        """Check if current user is the organizer of a given event."""
        from app import Event
        event = self.db.get(Event, event_id)
        if event is None:
            return False
        return event.organizer_id == self.user_id

    def _is_teacher_of_event(self, event_id):
        """Check if current teacher is assigned to a given event."""
        from app import Event, EventFaculty
        event = self.db.get(Event, event_id)
        if event is None:
            return False
        if event.organizer_id == self.user_id:
            return True
        return EventFaculty.query.filter_by(event_id=event_id, faculty_id=self.user_id).first() is not None

    def _get_nearby_week(self):
        """Return (start_date, end_date) for the current/next week."""
        now = datetime.utcnow()
        # Start of current week (Monday)
        start_of_week = now.date() - timedelta(days=now.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        return start_of_week, end_of_week

    # ============================================================
    # STUDENT QUERIES
    # ============================================================

    def student_get_upcoming_events(self, category=None):
        """Get upcoming events, optionally filtered by category.

        Students can see all public upcoming events - no RBAC restriction.
        """
        from app import Event, Registration

        now = datetime.utcnow()
        query = Event.query.filter(
            Event.status == "approved",
            Event.date >= now.date(),
        )
        if category:
            query = query.filter(Event.category == category)
        events = query.order_by(Event.date.asc()).all()

        result = []
        for e in events:
            seats = max(0, (e.capacity or 0) - Registration.query.filter(
                Registration.event_id == e.id,
                Registration.status.in_(["confirmed", "pending", "approved"]),
            ).count())
            result.append({
                "id": e.id,
                "title": e.title,
                "category": e.category,
                "date": e.date.strftime('%d %b %Y') if e.date else "—",
                "start_time": e.start_time,
                "end_time": e.end_time,
                "venue": e.venue,
                "fee": e.fee,
                "seats_left": seats,
                "status": e.status,
            })
        return {"events": result, "count": len(result)}

    def student_get_registrations(self):
        """Get events the student has registered for.

        RBAC: Student can only see their own registrations.
        """
        from app import Registration

        registrations = Registration.query.filter_by(user_id=self.user_id).order_by(
            Registration.registered_at.desc()
        ).all()

        result = []
        for r in registrations:
            result.append({
                "id": r.id,
                "event_id": r.event_id,
                "event_title": r.event.title if r.event else "—",
                "event_date": r.event.date.strftime('%d %b %Y') if r.event and r.event.date else "—",
                "event_venue": r.event.venue if r.event else "—",
                "category": r.event.category if r.event else "—",
                "status": r.status,
                "payment_status": r.payment_status,
                "attended": r.attended,
                "registered_at": r.registered_at.strftime('%d %b %Y') if r.registered_at else "—",
            })
        return {"registrations": result, "count": len(result)}

    def student_get_next_event(self):
        """Find the student's next upcoming event (earliest future event they registered for)."""
        from app import Registration, Event

        # Get registrations for upcoming events
        now = datetime.utcnow()
        regs = self.db.query(Registration).join(Event).filter(
            Registration.user_id == self.user_id,
            Event.date >= now.date(),
            Registration.status.in_(["confirmed", "pending", "approved"]),
        ).order_by(Event.date.asc()).all()

        if not regs:
            return None

        # Sort by date and time
        def event_datetime(reg):
            d = reg.event.date if reg.event else None
            t = reg.event.start_time if reg.event else "00:00"
            if d and t:
                try:
                    from datetime import time as _time
                    from datetime import datetime as _dt
                    return _dt.combine(d, _time.fromisoformat(t))
                except (ValueError, AttributeError):
                    return d
            return d

        regs.sort(key=lambda r: (event_datetime(r) or datetime.utcnow()))
        next_reg = regs[0]
        return {
            "event_id": next_reg.event_id,
            "title": next_reg.event.title if next_reg.event else "—",
            "category": next_reg.event.category if next_reg.event else "—",
            "date": next_reg.event.date.strftime('%d %b %Y') if next_reg.event and next_reg.event.date else "—",
            "start_time": next_reg.event.start_time if next_reg.event else "—",
            "venue": next_reg.event.venue if next_reg.event else "—",
            "status": next_reg.status,
        }

    def student_get_attendance_count(self):
        """Count how many events the student has attended."""
        from app import Registration

        attended_count = Registration.query.filter_by(
            user_id=self.user_id,
            attended=True,
        ).count()

        total_registered = Registration.query.filter_by(user_id=self.user_id).count()

        return {
            "attended": attended_count,
            "total_registered": total_registered,
            "upcoming": total_registered - attended_count,
        }

    def student_get_certificates(self):
        """Check if the student has any certificates."""
        from app import DigitalCertificate, Registration

        certs = self.db.query(DigitalCertificate).join(Registration).filter(
            Registration.user_id == self.user_id,
        ).all()

        result = []
        for c in certs:
            reg = c.registration
            result.append({
                "certificate_id": c.id,
                "certificate_code": c.certificate_code,
                "achievement": c.achievement,
                "event_title": reg.event.title if reg and reg.event else "—",
                "event_date": reg.event.date.strftime('%d %b %Y') if reg and reg.event and reg.event.date else "—",
                "issued_date": c.issued_date.strftime('%d %b %Y') if c.issued_date else "—",
                "verified": c.verified,
            })
        return {"certificates": result, "count": len(result)}

    def student_get_recommendations(self):
        """Get AI recommendations for the student based on their profile."""
        from app import EventRecommendation, Event, Registration

        # Get events the student hasn't registered for yet
        registered_event_ids = self.db.query(Registration.event_id).filter_by(
            user_id=self.user_id
        ).with_entities(Registration.event_id).all()
        registered_ids = {r[0] for r in registered_event_ids}

        now = datetime.utcnow()
        future_events = Event.query.filter(
            Event.status == "approved",
            Event.date >= now.date(),
        ).all()

        recommendations = []
        for e in future_events:
            if e.id in registered_ids:
                continue
            rec = EventRecommendation.query.filter_by(
                user_id=self.user_id, event_id=e.id
            ).first()
            score = rec.score if rec else 0
            reason = rec.reason if rec else "Based on your profile and interests"
            recommendations.append({
                "event_id": e.id,
                "title": e.title,
                "category": e.category,
                "date": e.date.strftime('%d %b %Y') if e.date else "—",
                "venue": e.venue,
                "score": score,
                "reason": reason,
            })

        recommendations.sort(key=lambda x: x["score"], reverse=True)
        return {"recommendations": recommendations[:10], "count": len(recommendations)}

    # ============================================================
    # ORGANIZER QUERIES
    # ============================================================

    def organizer_get_events(self):
        """Get all events organized by the current user.

        RBAC: Organizer can only see their own events.
        """
        from app import Event, Registration

        events = Event.query.filter_by(organizer_id=self.user_id).order_by(
            Event.date.desc()
        ).all()

        result = []
        for e in events:
            registered = Registration.query.filter(
                Registration.event_id == e.id,
                Registration.status.in_(["confirmed", "pending", "approved"]),
            ).count()
            result.append({
                "id": e.id,
                "title": e.title,
                "category": e.category,
                "date": e.date.strftime('%d %b %Y') if e.date else "—",
                "venue": e.venue,
                "capacity": e.capacity,
                "registered": registered,
                "seats_left": max(0, (e.capacity or 0) - registered),
                "fee": e.fee,
                "status": e.status,
            })
        return {"events": result, "count": len(result)}

    def organizer_get_event_registrations(self, event_id):
        """Get student registrations for a specific event.

        RBAC: Organizer can only access registrations for their own events.
        """
        from app import Registration

        if not self._is_organizer_of_event(event_id):
            return {"error": "Access denied. You are not the organizer of this event.", "event_id": event_id}

        registrations = Registration.query.filter_by(event_id=event_id).order_by(
            Registration.registered_at.desc()
        ).all()

        result = []
        for r in registrations:
            result.append({
                "id": r.id,
                "student_name": r.user.name,
                "roll_no": r.user.roll_no or "—",
                "email": r.user.email,
                "department": r.user.department or "—",
                "course": r.user.course or "—",
                "status": r.status,
                "payment_status": r.payment_status,
                "attended": r.attended,
                "registered_at": r.registered_at.strftime('%d %b %Y %H:%M') if r.registered_at else "—",
            })

        stats = {
            "total": len(result),
            "confirmed": sum(1 for r in result if r["status"] == "confirmed"),
            "pending": sum(1 for r in result if r["status"] == "pending"),
            "rejected": sum(1 for r in result if r["status"] == "rejected"),
            "waitlisted": sum(1 for r in result if r["status"] == "waitlisted"),
            "attended": sum(1 for r in result if r["attended"]),
        }
        return {"registrations": result, "stats": stats, "event_id": event_id}

    def organizer_get_seats_left(self, event_id):
        """Get available seats for an event.

        RBAC: Organizer can only check seats for their own events.
        """
        from app import Event, Registration

        if not self._is_organizer_of_event(event_id):
            return {"error": "Access denied. You are not the organizer of this event.", "event_id": event_id}

        event = self.db.get(Event, event_id)
        if event is None:
            return {"error": "Event not found.", "event_id": event_id}

        registered = Registration.query.filter(
            Registration.event_id == event_id,
            Registration.status.in_(["confirmed", "pending", "approved"]),
        ).count()

        return {
            "event_id": event_id,
            "title": event.title,
            "capacity": event.capacity,
            "registered": registered,
            "seats_left": max(0, (event.capacity or 0) - registered),
            "is_full": registered >= (event.capacity or 0),
        }

    def organizer_get_volunteers(self, event_id):
        """Get volunteers assigned to an event.

        RBAC: Organizer can only see volunteers for their own events.
        """
        from app import Volunteer

        if not self._is_organizer_of_event(event_id):
            return {"error": "Access denied. You are not the organizer of this event.", "event_id": event_id}

        volunteers = Volunteer.query.filter_by(event_id=event_id).all()

        result = []
        for v in volunteers:
            result.append({
                "id": v.id,
                "name": v.name,
                "email": v.email or "—",
                "task": v.task or "—",
                "status": v.status,
            })
        return {"volunteers": result, "count": len(result), "event_id": event_id}

    def organizer_get_event_stats(self, event_id=None):
        """Get statistics for the organizer's events.

        RBAC: Organizer can only access their own events.
        """
        from app import Event, Registration

        if event_id:
            if not self._is_organizer_of_event(event_id):
                return {"error": "Access denied.", "event_id": event_id}
            events = [self.db.get(Event, event_id)]
        else:
            events = Event.query.filter_by(organizer_id=self.user_id).all()

        total_events = len(events)
        total_registrations = 0
        total_attended = 0
        total_revenue = 0.0

        for e in events:
            regs = Registration.query.filter_by(event_id=e.id).all()
            total_registrations += len(regs)
            total_attended += sum(1 for r in regs if r.attended)
            if e.fee:
                total_revenue += e.fee * sum(1 for r in regs if r.status == "confirmed")

        return {
            "total_events": total_events,
            "total_registrations": total_registrations,
            "total_attended": total_attended,
            "total_revenue": total_revenue,
        }

    # ============================================================
    # ADMIN / TEACHER QUERIES
    # ============================================================

    def admin_get_weekly_events(self):
        """Get events happening this week.

        RBAC: Admin/Teacher can see all campus events.
        """
        from app import Event, Registration

        start, end = self._get_nearby_week()
        events = Event.query.filter(
            Event.date >= start,
            Event.date <= end,
            Event.status == "approved",
        ).order_by(Event.date.asc()).all()

        result = []
        for e in events:
            registered = Registration.query.filter(
                Registration.event_id == e.id,
                Registration.status.in_(["confirmed", "pending", "approved"]),
            ).count()
            result.append({
                "id": e.id,
                "title": e.title,
                "category": e.category,
                "date": e.date.strftime('%d %b %Y') if e.date else "—",
                "start_time": e.start_time,
                "end_time": e.end_time,
                "venue": e.venue,
                "organizer": e.organizer.name if e.organizer else "—",
                "capacity": e.capacity,
                "registered": registered,
                "seats_left": max(0, (e.capacity or 0) - registered),
                "status": e.status,
            })
        return {"events": result, "count": len(result), "week_start": start.strftime('%d %b %Y'), "week_end": end.strftime('%d %b %Y')}

    def admin_get_venue_utilization(self):
        """Get venue utilization data.

        RBAC: Admin/Teacher can see all venues.
        """
        from app import Event, Registration, Venue

        now = datetime.utcnow()
        venues = Venue.query.filter_by(status="active").all()
        result = []

        for v in venues:
            events_at_venue = Event.query.filter(
                Event.venue == v.name,
                Event.date >= now.date(),
            ).all()
            total_events = len(events_at_venue)
            total_capacity = sum((e.capacity or 0) for e in events_at_venue)
            registered = Registration.query.filter(
                Registration.event_id.in_([e.id for e in events_at_venue]),
                Registration.status.in_(["confirmed", "pending", "approved"]),
            ).count()
            result.append({
                "venue_name": v.name,
                "building": v.building,
                "capacity": v.capacity,
                "upcoming_events": total_events,
                "total_registered": registered,
                "total_capacity": total_capacity,
                "utilization_pct": round(registered / total_capacity * 100, 1) if total_capacity > 0 else 0,
                "status": "heavily utilized" if (total_capacity > 0 and registered / total_capacity * 100 > 80) else "available",
            })

        result.sort(key=lambda x: x["utilization_pct"], reverse=True)
        return {"venues": result, "count": len(result)}

    def admin_get_event_conflicts(self):
        """Detect potential event conflicts (same date/time/venue overlap).

        RBAC: Admin/Teacher can see all events.
        """
        from app import Event

        now = datetime.utcnow()
        upcoming = Event.query.filter(
            Event.date >= now.date(),
            Event.status == "approved",
        ).order_by(Event.date.asc()).all()

        conflicts = []
        for i, e1 in enumerate(upcoming):
            for e2 in upcoming[i + 1:]:
                if e1.date != e2.date:
                    continue
                # Check venue overlap
                if e1.venue == e2.venue:
                    conflicts.append({
                        "event_1": {"id": e1.id, "title": e1.title, "time": f"{e1.start_time} - {e1.end_time}"},
                        "event_2": {"id": e2.id, "title": e2.title, "time": f"{e2.start_time} - {e2.end_time}"},
                        "venue": e1.venue,
                        "date": e1.date.strftime('%d %b %Y'),
                        "type": "venue_conflict",
                        "severity": "high" if e1.start_time == e2.start_time else "medium",
                    })
                # Check category overlap (same category on same day)
                elif e1.category == e2.category:
                    conflicts.append({
                        "event_1": {"id": e1.id, "title": e1.title, "time": f"{e1.start_time} - {e1.end_time}"},
                        "event_2": {"id": e2.id, "title": e2.title, "time": f"{e2.start_time} - {e2.end_time}"},
                        "venue": "N/A (category competition)",
                        "date": e1.date.strftime('%d %b %Y'),
                        "type": "category_concurrency",
                        "severity": "low",
                    })

        return {"conflicts": conflicts, "count": len(conflicts)}

    def admin_get_all_events(self, status=None, category=None):
        """Get all events with optional filters.

        RBAC: Admin/Teacher can see all events.
        """
        from app import Event, Registration

        query = Event.query
        if status:
            query = query.filter(Event.status == status)
        if category:
            query = query.filter(Event.category == category)
        events = query.order_by(Event.date.desc()).all()

        result = []
        for e in events:
            registered = self.db.query(__import__('app', fromlist=['Registration']).Registration).filter(
                Registration.event_id == e.id,
                Registration.status.in_(["confirmed", "pending", "approved"]),
            ).count()
            result.append({
                "id": e.id,
                "title": e.title,
                "category": e.category,
                "date": e.date.strftime('%d %b %Y') if e.date else "—",
                "venue": e.venue,
                "organizer": e.organizer.name if e.organizer else "—",
                "capacity": e.capacity,
                "registered": registered,
                "seats_left": max(0, (e.capacity or 0) - registered),
                "status": e.status,
            })
        return {"events": result, "count": len(result)}

    def admin_get_user_stats(self):
        """Get campus-wide user statistics.

        RBAC: Admin only.
        """
        from app import User

        users = User.query.all()
        return {
            "total_users": len(users),
            "students": sum(1 for u in users if u.role == "student"),
            "organizers": sum(1 for u in users if u.role == "organizer"),
            "admins": sum(1 for u in users if u.role == "admin"),
            "teachers": sum(1 for u in users if u.role == "teacher"),
            "volunteers": sum(1 for u in users if u.role == "volunteer"),
        }

    # ============================================================
    # GENERAL QUERIES (all roles)
    # ============================================================

    def get_all_categories(self):
        """Get all event categories."""
        from app import Event
        categories = self.db.query(Event.category).distinct().all()
        return [c[0] for c in categories]

    def get_announcements(self):
        """Get campus announcements."""
        from app import Notice
        notices = Notice.query.filter_by(status="published").order_by(
            Notice.published_at.desc()
        ).limit(10).all()
        result = []
        for n in notices:
            result.append({
                "id": n.id,
                "title": n.title,
                "category": n.category,
                "published_at": n.published_at.strftime('%d %b %Y') if n.published_at else "—",
            })
        return {"announcements": result, "count": len(result)}

    def get_user_profile(self):
        """Get the current user's profile info (safe to expose)."""
        from app import StudentProfile, OrganizerProfile, AdminProfile, FacultyProfile

        profile = {
            "name": self.current_user.name,
            "email": self.current_user.email,
            "role": self.current_user.role,
            "department": self.current_user.department or "—",
            "mobile": self.current_user.mobile or "—",
        }

        if self.current_user.role == "student":
            sp = StudentProfile.query.filter_by(user_id=self.user_id).first()
            if sp:
                profile["student_id"] = sp.student_id or "—"
                profile["course"] = sp.course or "—"
                profile["semester"] = sp.semester or "—"
        elif self.current_user.role == "organizer":
            op = OrganizerProfile.query.filter_by(user_id=self.user_id).first()
            if op:
                profile["employee_id"] = op.employee_id or "—"
                profile["title"] = op.title or "—"
        elif self.current_user.role == "teacher":
            fp = FacultyProfile.query.filter_by(user_id=self.user_id).first()
            if fp:
                profile["employee_id"] = fp.employee_id or "—"
                profile["designation"] = fp.designation or "—"
        elif self.current_user.role == "admin":
            ap = AdminProfile.query.filter_by(user_id=self.user_id).first()
            if ap:
                profile["employee_id"] = ap.employee_id or "—"

        return profile

    # ============================================================
    # MAIN QUERY RESOLVER
    # ============================================================

    def resolve_query(self, message: str) -> dict:
        """Classify the user's query and retrieve relevant data.

        This is the main entry point. It:
        1. Classifies the intent of the message
        2. Validates RBAC for the requested data
        3. Retrieves relevant data through safe ORM queries
        4. Returns structured data for the AI to use

        Returns a dict with:
            - "intent": classified intent
            - "data": the retrieved data
            - "context": additional context for AI
            - "error": any error message
        """
        if not self.is_authorized():
            return {
                "intent": "unauthorized",
                "data": None,
                "context": {},
                "error": "You must be logged in to use the campus assistant.",
            }

        message_lower = (message or "").lower().strip()
        role = self.user_role

        # Determine intent from message keywords
        intent = self._classify_intent(message_lower)

        # Route to appropriate data retrieval based on intent and role
        try:
            if intent in ("upcoming_events", "events_this_week", "technical_events", "events_by_category"):
                if role in ("student",):
                    data = self.student_get_upcoming_events(
                        category=self._extract_category(message_lower)
                    )
                else:
                    data = self.admin_get_weekly_events()

            elif intent == "my_registrations":
                if role == "student":
                    data = self.student_get_registrations()
                else:
                    data = self._get_registrations_for_role()

            elif intent == "next_event":
                if role == "student":
                    data = self.student_get_next_event()
                else:
                    data = self._get_next_event_for_role()

            elif intent == "attendance_count":
                if role == "student":
                    data = self.student_get_attendance_count()
                else:
                    return {
                        "intent": intent,
                        "data": None,
                        "context": {"message": message},
                        "error": "This feature is available for students only. Your role does not have access to attendance records via the assistant.",
                    }

            elif intent == "certificates":
                if role == "student":
                    data = self.student_get_certificates()
                else:
                    return {
                        "intent": intent,
                        "data": None,
                        "context": {"message": message},
                        "error": "Certificate information is available for students only through the assistant.",
                    }

            elif intent in ("organizer_events", "my_events"):
                if role in ("organizer", "teacher", "admin"):
                    data = self.organizer_get_events()
                else:
                    data = {"error": "Only organizers can view their events through the assistant."}

            elif intent in ("event_registrations", "registrations_for_event", "student_list"):
                if role in ("organizer", "teacher", "admin"):
                    event_id = self._extract_event_id(message_lower) or self._extract_event_id_from_context(message)
                    if event_id:
                        data = self.organizer_get_event_registrations(event_id)
                    else:
                        data = {"error": "Please specify which event you want to check registrations for."}
                else:
                    data = {"error": "Only organizers and teachers can view event registrations."}

            elif intent in ("seats_left", "available_seats", "capacity"):
                if role in ("organizer", "teacher", "admin"):
                    event_id = self._extract_event_id(message_lower) or self._extract_event_id_from_context(message)
                    if event_id:
                        data = self.organizer_get_seats_left(event_id)
                    else:
                        data = {"error": "Please specify which event to check seats for."}
                else:
                    data = {"error": "Only organizers and teachers can check seat availability."}

            elif intent in ("volunteers", "volunteer_list"):
                if role in ("organizer", "teacher", "admin"):
                    event_id = self._extract_event_id(message_lower) or self._extract_event_id_from_context(message)
                    if event_id:
                        data = self.organizer_get_volunteers(event_id)
                    else:
                        data = {"error": "Please specify which event to check volunteers for."}
                else:
                    data = {"error": "Only organizers and teachers can view volunteer assignments."}

            elif intent in ("weekly_events", "events_this_week_admin", "campus_events"):
                if role in ("admin", "teacher"):
                    data = self.admin_get_weekly_events()
                else:
                    data = {"error": "Campus-wide event overview is available for admins and teachers only."}

            elif intent in ("venue_utilization", "venue_usage", "heavily_utilized"):
                if role in ("admin", "teacher"):
                    data = self.admin_get_venue_utilization()
                else:
                    data = {"error": "Venue utilization data is available for admins and teachers only."}

            elif intent in ("event_conflicts", "schedule_conflicts"):
                if role in ("admin", "teacher"):
                    data = self.admin_get_event_conflicts()
                else:
                    data = {"error": "Event conflict detection is available for admins and teachers only."}

            elif intent == "recommendations":
                if role == "student":
                    data = self.student_get_recommendations()
                else:
                    data = {"error": "Event recommendations are personalized for students."}

            elif intent == "user_stats":
                if role == "admin":
                    data = self.admin_get_user_stats()
                else:
                    data = {"error": "User statistics are available for admins only."}

            elif intent == "all_events":
                if role in ("admin", "teacher"):
                    data = self.admin_get_all_events()
                else:
                    data = {"error": "Viewing all events is available for admins and teachers."}

            elif intent == "profile":
                data = self.get_user_profile()

            elif intent == "announcements":
                data = self.get_announcements()

            else:
                # Default: try to get relevant data based on role
                if role == "student":
                    data = self.student_get_upcoming_events()
                elif role in ("organizer",):
                    data = self.organizer_get_events()
                elif role in ("admin", "teacher"):
                    data = self.admin_get_weekly_events()
                else:
                    data = {"error": "Unable to determine relevant information."}

            return {
                "intent": intent,
                "data": data,
                "context": {
                    "role": role,
                    "user_name": self.current_user.name,
                    "message": message,
                },
                "error": None,
            }

        except Exception as exc:
            return {
                "intent": "error",
                "data": None,
                "context": {"message": message, "role": role},
                "error": f"An error occurred while retrieving information: {str(exc)}",
            }

    def _classify_intent(self, message_lower: str) -> str:
        """Classify the intent of a user message."""
        # Organizer/admin specific queries (checked first to override "registered" keyword)
        if any(w in message_lower for w in ["registered for my event", "how many students registered", "how many students", "students registered"]):
            return "event_registrations"

        # Technical events
        if any(w in message_lower for w in ["technical", "hackathon", "coding", "web dev", "cyber", "data science", "robotics", "blockchain", "iot"]):
            if any(w in message_lower for w in ["this week", "coming", "upcoming", "next"]):
                return "upcoming_events"
            return "upcoming_events"

        # Events this week
        if any(w in message_lower for w in ["this week", "this's week", "week ahead", "coming week", "next 7 days"]):
            return "events_this_week"

        # My registrations (student personal data)
        if any(w in message_lower for w in ["registered", "my events", "my registrations", "registered for", "signed up", "enrolled"]):
            return "my_registrations"

        # Organizer queries
        if any(w in message_lower for w in ["seats", "available seats", "capacity", "volunteer", "volunteers"]):
            if "volunteer" in message_lower:
                return "volunteers"
            elif "seat" in message_lower or "capacity" in message_lower or "seats" in message_lower:
                return "seats_left"
            return "event_registrations"

        # Next event
        if any(w in message_lower for w in ["next event", "nearest event", "upcoming one", "first event", "nearest", "where is my next"]):
            return "next_event"

        # Attendance
        if any(w in message_lower for w in ["attended", "attendance", "how many events i", "events i have attended", "participated"]):
            return "attendance_count"

        # Certificates
        if any(w in message_lower for w in ["certificate", "certificates", "do i have", "my certificates", "certificate of"]):
            return "certificates"

        # Organizer queries
        if any(w in message_lower for w in ["registered for my event", "students registered", "how many students", "seats", "available seats", "capacity", "volunteer", "volunteers"]):
            if "volunteer" in message_lower:
                return "volunteers"
            elif "seat" in message_lower or "capacity" in message_lower or "seats" in message_lower:
                return "seats_left"
            elif "student" in message_lower or "registered" in message_lower:
                return "event_registrations"

        # Venue utilization
        if any(w in message_lower for w in ["venue", "utilized", "utilization", "heavily", "busy venue", "popular venue"]):
            return "venue_utilization"

        # Event conflicts
        if any(w in message_lower for w in ["conflict", "overlap", "clash", "schedule conflict", "time conflict"]):
            return "event_conflicts"

        # Weekly events for admin/teacher
        if any(w in message_lower for w in ["happening this week", "events this week", "campus events", "all events"]):
            return "weekly_events"

        # Recommendations
        if any(w in message_lower for w in ["recommend", "suggest", "what should i", "i might like", "interest"]):
            return "recommendations"

        # User stats / admin queries
        if any(w in message_lower for w in ["how many users", "user stats", "statistics", "total students"]):
            return "user_stats"

        # Announcements
        if any(w in message_lower for w in ["announcement", "notice", "notices"]):
            return "announcements"

        # All events
        if any(w in message_lower for w in ["all events", "list of events", "every event"]):
            return "all_events"

        # Profile
        if any(w in message_lower for w in ["my profile", "profile info", "about me", "my info"]):
            return "profile"

        # Default
        return "general"

    def _extract_category(self, message_lower: str):
        """Extract a category from the message."""
        categories = ["academic", "technical", "cultural", "sports", "workshop", "entrepreneurship", "social"]
        for cat in categories:
            if cat in message_lower:
                return cat.title()
        return None

    def _extract_event_id(self, message_lower: str):
        """Extract an event ID from message text."""
        import re
        match = re.search(r'event\s*(\d+)', message_lower)
        if match:
            return int(match.group(1))
        return None

    def _extract_event_id_from_context(self, message: str):
        """Try to extract event reference from context."""
        import re
        match = re.search(r'event\s*#?\s*(\d+)', message, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    def _get_registrations_for_role(self):
        """Fallback for non-student roles."""
        return {"error": "Registration details are personal to each student."}

    def _get_next_event_for_role(self):
        """Fallback for non-student roles."""
        return {"error": "Next event information is personalized for each student."}
