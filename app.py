import os
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from io import BytesIO
from functools import wraps

import qrcode
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request, flash, send_file, abort, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from cems.extensions import csrf, db, limiter, login_manager, migrate
from cems.services import (
    audit,
    available_seats,
    cancel_registration,
    clean_text,
    create_mock_payment,
    ensure_ticket,
    event_display_status,
    event_history,
    mark_attendance,
    notify,
    parse_custom_questions,
    parse_date,
    parse_time,
    process_waitlist,
    register_student,
    save_uploaded_file,
    schedule_registration_reminders,
    send_due_reminders,
    validate_event_payload,
)
from cems.domain import (
    AdminProfile,
    AuditLog,
    EventActivity,
    EventApprovalHistory,
    EventCategory,
    EventCustomField,
    EventCustomResponse,
    OrganizerProfile,
    Payment,
    Reminder,
    Role,
    StudentProfile,
    Ticket,
)
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import inspect as sa_inspect, text
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
# ==============================
# AGC CAMPUS ECOSYSTEM DATA
# ==============================

AGC_INFO = {
    "about": {
        "title": "About AGC",
        "description": """
        Amritsar Group of Colleges (AGC) is an autonomous institution
        focused on quality education, innovation, entrepreneurship,
        research, industry exposure and global opportunities.
        """
    },

    "naac": {
        "title": "NAAC A Grade",
        "description": """
        AGC has been conferred with NAAC 'A' Grade accreditation,
        reflecting its commitment to academic quality and institutional excellence.
        """
    },

    "aicte": {
        "title": "AICTE Approval",
        "description": """
        AGC offers programs aligned with applicable AICTE requirements
        and academic standards.
        """
    },

    "pci": {
        "title": "PCI Approval",
        "description": """
        Pharmacy programs at AGC are aligned with Pharmacy Council
        of India requirements.
        """
    },

    "ikgptu": {
        "title": "IKGPTU Affiliation",
        "description": """
        AGC has academic association with I.K. Gujral Punjab Technical University
        for applicable programs.
        """
    },

    "iqac": {
        "title": "IQAC",
        "description": """
        Internal Quality Assurance Cell works towards continuous
        improvement of academic and institutional quality.
        """
    },

    "aqar": {
        "title": "AQAR Reports",
        "description": """
        Annual Quality Assurance Reports provide information about
        institutional quality initiatives and academic development.
        """
    },

    "aishe": {
        "title": "AISHE",
        "description": """
        All India Survey on Higher Education related institutional information.
        """
    },

    "iso": {
        "title": "ISO",
        "description": """
        AGC follows quality-oriented institutional processes and standards.
        """
    },

    "nptel": {
        "title": "NPTEL",
        "description": """
        Students can benefit from NPTEL courses, certifications and
        digital learning opportunities.
        """
    }
}


# ==============================
# AGC CAMPUS MODULES
# ==============================

AGC_MODULES = {
    "academics": {
        "title": "Academics",
        "icon": "📚",
        "description": "Courses, departments, programs, academic information and learning resources."
    },

    "admissions": {
        "title": "Admissions",
        "icon": "🎓",
        "description": "Admission information, courses, eligibility and enquiry support."
    },

    "examination": {
        "title": "Examination",
        "icon": "📝",
        "description": "Date sheets, examination forms, results, re-appear information and notices."
    },

    "research": {
        "title": "Research",
        "icon": "🔬",
        "description": "Research, innovation, publications, conferences and development activities."
    },

    "placement": {
        "title": "Placement",
        "icon": "💼",
        "description": "Placement opportunities, companies, drives and student career support."
    },

    "alumni": {
        "title": "Alumni",
        "icon": "👥",
        "description": "Connect with AGC alumni, success stories and alumni activities."
    },

    "edc": {
        "title": "Entrepreneurship Development Cell",
        "icon": "🚀",
        "description": "Entrepreneurship, startup ideas, innovation and business development activities."
    },

    "grievance": {
        "title": "Grievance Redressal",
        "icon": "🛡️",
        "description": "Submit and track student grievances through the campus system."
    },

    "infrastructure": {
        "title": "Infrastructure",
        "icon": "🏫",
        "description": "Campus facilities, laboratories, library, hostel, sports and other infrastructure."
    },

    "life": {
        "title": "Life @ AGC",
        "icon": "🌟",
        "description": "Campus life, cultural activities, events, clubs, sports and student experiences."
    },

    "contact": {
        "title": "Contact Us",
        "icon": "📞",
        "description": "Find important AGC contact information and campus directory."
    }
}


# ==============================
# AGC STATISTICS
# ==============================

AGC_STATS = [
    {
        "number": "1475+",
        "title": "Students",
        "description": "Students connected with the AGC academic ecosystem."
    },
    {
        "number": "20+",
        "title": "Years",
        "description": "More than two decades of academic and professional education."
    },
    {
        "number": "25",
        "title": "Programs",
        "description": "Professional undergraduate and postgraduate programs."
    },
    {
        "number": "425+",
        "title": "Jobs",
        "description": "Students secured opportunities through campus placements."
    }
]


# ==============================
# LATEST AGC NOTICES
# ==============================

AGC_NOTICES = [
    "Final Re-appear Date sheet for May-2026 End Semester Examinations",
    "Revised Re-appear Date sheet for Nov-2025 End Semester Examinations",
    "Regular 1st year Date sheet for Nov-2025 End Semester Examinations",
    "Final Re-appear Date sheet for Nov-2025 End Semester Examinations",
    "Proposed Re-appear Date sheet for Nov-2025 End Semester Examinations",
    "Regular Date sheet for Nov-2025 End Semester Examinations",
    "Examination Forms (Re-appear) for Nov-2025 Session",
    "Commencement of Classes session (July-Dec 2025)",
    "AGC NEST 2026",
    "AICTE VAANI Seminar"
]
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
db_url = os.getenv("DATABASE_URL", "sqlite:///cems.db")
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024

db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)
login_manager.login_view = "login"
csrf.init_app(app)
limiter.init_app(app)

COLLEGE = os.getenv("COLLEGE_NAME", "Amritsar Group of Colleges")
SHORT = os.getenv("COLLEGE_SHORT", "AGC")
AGC_PROFILE = {
    "tagline": "Autonomous Institution • Amritsar, Punjab",
    "status": "Autonomous",
    "naac": "NAAC A Grade",
    "approvals": ["AICTE", "PCI"],
    "affiliation": "IKGPTU",
    "quality": ["IQAC", "ISO", "NPTEL", "AISHE"],
    "years": "20+ Years",
    "students": "1475+ Students",
    "programs": "25 Programs",
    "placement_highlight": "425+ Jobs reported in the supplied AGC profile content",
    "address": "12 Km Stone, Amritsar-Jalandhar, G.T. Road, Amritsar-143001 (PB), India",
    "phone_primary": "+91 88720 09951",
    "phone_support": "+91 88720 09950",
    "support_line": "24/7 Support Line",
    "email": "info@agc.edu.in",
    "whatsapp": "https://wa.me/918872009950?text=Hello%20AGC%20Support%2C%20I%20need%20help%20with%20campus%20events%20and%20admissions.",
}

AGC_UPDATES = [
    "Final Re-appear Date Sheet for May-2026 End Semester Examinations",
    "AGC NEST 2026 — Scholarship opportunity",
    "AI Centre of Excellence — upcoming initiatives",
    "Certification Course in Artificial Intelligence and Machine Learning",
    "Campus placements and industry-integrated learning updates",
]

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    mobile = db.Column(db.String(20))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default="student")
    department = db.Column(db.String(100))
    roll_no = db.Column(db.String(50))
    student_id = db.Column(db.String(80), unique=True)
    employee_id = db.Column(db.String(80), unique=True)
    course = db.Column(db.String(100))
    semester = db.Column(db.String(20))
    profile_image = db.Column(db.String(255))
    settings_json = db.Column(db.JSON, default=dict)
    last_login_at = db.Column(db.DateTime)
    is_verified = db.Column(db.Boolean, default=False)
    is_active_account = db.Column(db.Boolean, default=True)
    verification_token = db.Column(db.String(100))
    reset_token = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        return bool(self.is_active_account)

    def record_login(self):
        self.last_login_at = datetime.utcnow()

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    event_type = db.Column(db.String(30), default="free")
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(20), nullable=False)
    end_time = db.Column(db.String(20), nullable=False)
    venue = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    highlights = db.Column(db.Text)
    banner = db.Column(db.String(255))
    capacity = db.Column(db.Integer, default=100)
    registration_start = db.Column(db.Date)
    registration_deadline = db.Column(db.Date)
    fee = db.Column(db.Float, default=0)
    status = db.Column(db.String(30), default="pending")
    published_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    cancellation_reason = db.Column(db.Text)
    results = db.Column(db.Text)
    documents_json = db.Column(db.JSON, default=list)
    custom_questions_json = db.Column(db.JSON, default=list)
    contact_person = db.Column(db.String(120))
    contact_email = db.Column(db.String(160))
    contact_phone = db.Column(db.String(30))
    rules = db.Column(db.Text)
    eligibility = db.Column(db.Text)
    contact_info = db.Column(db.Text)
    image = db.Column(db.String(255))
    rejection_reason = db.Column(db.Text)
    change_status = db.Column(db.String(30), default="none")
    original_data = db.Column(db.JSON)
    main_guest = db.Column(db.String(120))
    chief_guest = db.Column(db.String(120))
    organizer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    organizer = db.relationship("User", backref="organized_events")

class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_code = db.Column(db.String(30), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"), nullable=False)
    status = db.Column(db.String(30), default="confirmed")
    payment_status = db.Column(db.String(30), default="free")
    attended = db.Column(db.Boolean, default=False)
    checkin_time = db.Column(db.DateTime)
    terms_accepted = db.Column(db.Boolean, default=False)
    cancellation_reason = db.Column(db.Text)
    cancelled_at = db.Column(db.DateTime)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", backref="registrations")
    event = db.relationship("Event", backref="registrations")

    __table_args__ = (
        db.UniqueConstraint("user_id", "event_id", name="uq_registration_user_event"),
    )

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    message = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default="general")
    action_url = db.Column(db.String(255))
    expires_at = db.Column(db.DateTime)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", backref="notifications")

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey("registration.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Venue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    location = db.Column(db.String(200))
    capacity = db.Column(db.Integer, default=100)
    available = db.Column(db.Boolean, default=True)

class Volunteer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160))
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    task = db.Column(db.String(160))
    status = db.Column(db.String(30), default="Assigned")

class Judge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160))
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    criteria = db.Column(db.String(250))

class Sponsor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    contact = db.Column(db.String(160))
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    contribution = db.Column(db.Float, default=0)

# ===== 50 ADVANCED FEATURES DATABASE MODELS =====

# 1-5: AI Recommendation & Discovery
class EventRecommendation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    score = db.Column(db.Float, default=0)  # 0-100 recommendation score
    reason = db.Column(db.String(255))  # Why recommended
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# 6-7: Venue & Booking
class VenueBooking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    venue_id = db.Column(db.Integer, db.ForeignKey("venue.id"))
    booking_date = db.Column(db.DateTime)
    status = db.Column(db.String(30), default="confirmed")  # confirmed, cancelled, pending
    notes = db.Column(db.Text)

class EventClashDetection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id_1 = db.Column(db.Integer, db.ForeignKey("event.id"))
    event_id_2 = db.Column(db.Integer, db.ForeignKey("event.id"))
    clash_severity = db.Column(db.String(20))  # high, medium, low
    resolution = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# 8-12: Attendance & Recognition
class AttendanceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey("registration.id"), unique=True, nullable=False)
    check_in_time = db.Column(db.DateTime)
    check_out_time = db.Column(db.DateTime)
    duration_minutes = db.Column(db.Integer)
    method = db.Column(db.String(50))  # qr_scan, face_recognition, manual
    status = db.Column(db.String(30), default="checked_in")
    scanned_by = db.Column(db.Integer, db.ForeignKey("user.id"))

class EventBudget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    total_budget = db.Column(db.Float)
    spent = db.Column(db.Float, default=0)
    category = db.Column(db.String(100))  # catering, venue, decor, etc
    status = db.Column(db.String(30), default="approved")

class VendorManagement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    vendor_name = db.Column(db.String(150))
    vendor_type = db.Column(db.String(100))  # catering, decor, security, etc
    contact = db.Column(db.String(160))
    amount = db.Column(db.Float)
    status = db.Column(db.String(30), default="pending")  # pending, confirmed, completed

class SponsorshipManagement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    sponsor_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    amount = db.Column(db.Float)
    tier = db.Column(db.String(50))  # platinum, gold, silver, bronze
    roi_tracking = db.Column(db.Float, default=0)  # ROI percentage
    deliverables = db.Column(db.Text)

# 13-14: Digital Passes & VIP
class DigitalEventPass(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey("registration.id"))
    pass_code = db.Column(db.String(100), unique=True)
    pass_type = db.Column(db.String(50))  # standard, vip, gold, platinum
    benefits = db.Column(db.Text)  # Extra benefits for VIP
    valid_from = db.Column(db.DateTime)
    valid_until = db.Column(db.DateTime)

class VIPGuestManagement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    guest_name = db.Column(db.String(120))
    guest_type = db.Column(db.String(50))  # keynote, judge, sponsor, vip
    special_requirements = db.Column(db.Text)
    arrival_time = db.Column(db.DateTime)
    dedicated_handler = db.Column(db.String(120))

# 15-17: Volunteer Management
class VolunteerAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    volunteer_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    task = db.Column(db.String(200))
    shift_start = db.Column(db.DateTime)
    shift_end = db.Column(db.DateTime)
    status = db.Column(db.String(30), default="assigned")

class VolunteerPerformance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    volunteer_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    rating = db.Column(db.Float)  # 1-5
    attendance = db.Column(db.Boolean, default=False)
    hours_worked = db.Column(db.Float)
    feedback = db.Column(db.Text)
    skills_demonstrated = db.Column(db.Text)

# 18-20: Workflow & Emergency
class EventTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    assigned_to = db.Column(db.Integer, db.ForeignKey("user.id"))
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    status = db.Column(db.String(30), default="pending")  # pending, in_progress, completed
    priority = db.Column(db.String(20))  # high, medium, low
    due_date = db.Column(db.DateTime)

class EventEmergency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    alert_type = db.Column(db.String(100))  # medical, security, crowd, weather, etc
    severity = db.Column(db.String(20))  # critical, high, medium, low
    description = db.Column(db.Text)
    response_team = db.Column(db.String(200))
    resolved = db.Column(db.Boolean, default=False)
    resolution_time = db.Column(db.DateTime)

# 21-24: Certificates & Portfolio
class LostAndFound(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    item_description = db.Column(db.String(255))
    found_by = db.Column(db.String(120))
    location = db.Column(db.String(200))
    status = db.Column(db.String(30), default="unclaimed")  # unclaimed, claimed, disposed
    claimed_by = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DigitalCertificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey("registration.id"))
    certificate_code = db.Column(db.String(100), unique=True)
    achievement = db.Column(db.String(200))
    issued_date = db.Column(db.DateTime, default=datetime.utcnow)
    verified = db.Column(db.Boolean, default=False)
    verification_code = db.Column(db.String(100))

class StudentEventPortfolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    total_events = db.Column(db.Integer, default=0)
    total_volunteer_hours = db.Column(db.Float, default=0)
    awards_won = db.Column(db.Integer, default=0)
    certificates_earned = db.Column(db.Integer, default=0)
    skills = db.Column(db.Text)
    bio = db.Column(db.Text)

class EventCredit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    credit_points = db.Column(db.Float, default=0)
    credit_type = db.Column(db.String(50))  # attendance, participation, volunteering
    approved = db.Column(db.Boolean, default=False)

# 25-29: Competition Management
class InterCollegeEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    participating_colleges = db.Column(db.Text)  # JSON list
    winner = db.Column(db.String(150))
    runner_up = db.Column(db.String(150))
    third_place = db.Column(db.String(150))

class OnlineCompetition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    competition_type = db.Column(db.String(100))  # quiz, coding, essay, etc
    platform = db.Column(db.String(100))
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    max_participants = db.Column(db.Integer)

class SportsTournament(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    sport_name = db.Column(db.String(100))
    tournament_format = db.Column(db.String(100))  # single_elim, double_elim, round_robin
    teams_count = db.Column(db.Integer, default=0)
    current_round = db.Column(db.Integer, default=1)

class LiveLeaderboard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey("online_competition.id"))
    participant_name = db.Column(db.String(120))
    score = db.Column(db.Float, default=0)
    rank = db.Column(db.Integer)
    status = db.Column(db.String(30))  # participating, completed, disqualified

# 30-34: Polling & Feedback Analysis
class EventPolling(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    question = db.Column(db.Text)
    poll_type = db.Column(db.String(50))  # live, post_event
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    live_results = db.Column(db.Text)  # JSON

class EventQA(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    question = db.Column(db.Text)
    asked_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    answered_by = db.Column(db.String(120))
    answer = db.Column(db.Text)
    upvotes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FeedbackSentiment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    feedback_text = db.Column(db.Text)
    sentiment = db.Column(db.String(20))  # positive, negative, neutral
    score = db.Column(db.Float)  # -1 to 1
    analyzed_at = db.Column(db.DateTime, default=datetime.utcnow)

class EventAnalytics(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    total_registered = db.Column(db.Integer, default=0)
    total_attended = db.Column(db.Integer, default=0)
    engagement_score = db.Column(db.Float)
    satisfaction_rating = db.Column(db.Float)
    roi = db.Column(db.Float)
    peak_time = db.Column(db.DateTime)

class AttendancePredictor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    predicted_attendance = db.Column(db.Integer)
    actual_attendance = db.Column(db.Integer)
    accuracy_percentage = db.Column(db.Float)
    prediction_date = db.Column(db.DateTime, default=datetime.utcnow)

# 35-37: Smart Features
class NoShowPrediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey("registration.id"))
    risk_score = db.Column(db.Float)  # 0-100
    predicted_to_noshow = db.Column(db.Boolean)
    reminder_sent = db.Column(db.Boolean, default=False)

class EventWaitlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    waitlist_position = db.Column(db.Integer)
    status = db.Column(db.String(30), default="waiting")
    notified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("event_id", "user_id", name="uq_waitlist_event_user"),
    )

class SeatAllocation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey("registration.id"))
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    seat_number = db.Column(db.String(50))
    section = db.Column(db.String(50))
    row = db.Column(db.String(10))
    allocated_at = db.Column(db.DateTime, default=datetime.utcnow)

# 38-41: Logistics Management
class FoodCoupon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey("registration.id"))
    coupon_code = db.Column(db.String(50), unique=True)
    coupon_value = db.Column(db.Float)
    redeemed = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime)

class CateringDemand(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    predicted_headcount = db.Column(db.Integer)
    actual_headcount = db.Column(db.Integer)
    food_categories = db.Column(db.Text)  # JSON
    dietary_requirements = db.Column(db.Text)

class TransportManagement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    vehicle_type = db.Column(db.String(50))  # bus, van, auto
    route = db.Column(db.String(255))
    capacity = db.Column(db.Integer)
    driver_name = db.Column(db.String(120))
    status = db.Column(db.String(30), default="available")

class ParkingManagement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    total_spots = db.Column(db.Integer)
    available_spots = db.Column(db.Integer)
    assigned_slots = db.Column(db.Text)  # JSON with user_id: slot_id

# 42-44: Security & Announcements
class SecurityManagement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    personnel_count = db.Column(db.Integer)
    security_level = db.Column(db.String(30))  # low, medium, high, vip
    checkpoints = db.Column(db.Text)
    incidents = db.Column(db.Text)

class CampusAnnouncement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    title = db.Column(db.String(255))
    content = db.Column(db.Text)
    channels = db.Column(db.Text)  # email, sms, push, dashboard
    priority = db.Column(db.String(20))  # high, normal, low
    published_at = db.Column(db.DateTime, default=datetime.utcnow)

class MultiChannelNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    message = db.Column(db.Text)
    channels = db.Column(db.Text)  # email, sms, push, in_app
    sent_at = db.Column(db.DateTime)
    read = db.Column(db.Boolean, default=False)

# 45-50: Administration & Compliance
class SponsorshipMarketplace(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    sponsorship_packages = db.Column(db.Text)  # JSON with packages and pricing
    interested_sponsors = db.Column(db.Text)  # JSON list
    confirmed_sponsors = db.Column(db.Text)

class ClubEventManagement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    club_name = db.Column(db.String(120))
    club_head = db.Column(db.String(120))
    budget_allocated = db.Column(db.Float)
    members_count = db.Column(db.Integer)
    approval_status = db.Column(db.String(30), default="pending")

class EquipmentInventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    item_name = db.Column(db.String(150))
    quantity = db.Column(db.Integer)
    condition = db.Column(db.String(50))  # good, fair, damaged
    assigned_to = db.Column(db.String(120))
    returned = db.Column(db.Boolean, default=False)

class EventApprovalWorkflow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    current_stage = db.Column(db.String(50))  # submitted, reviewed, approved, rejected
    approver_comments = db.Column(db.Text)
    required_documents = db.Column(db.Text)  # JSON
    approval_date = db.Column(db.DateTime)

class EventAudit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    audit_type = db.Column(db.String(50))  # financial, compliance, safety
    findings = db.Column(db.Text)
    status = db.Column(db.String(30), default="in_progress")
    completed_date = db.Column(db.DateTime)

class CommandCenter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    operator_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    live_metrics = db.Column(db.Text)  # JSON - attendance, crowd, mood, etc
    alerts = db.Column(db.Text)  # JSON array
    control_logs = db.Column(db.Text)  # JSON audit log
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(80), default="General")
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"))
    image = db.Column(db.String(255))
    attachment = db.Column(db.String(255))
    attachment_name = db.Column(db.String(255))
    published_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = db.Column(db.String(30), default="published")
    event = db.relationship("Event", backref="notices")
    author = db.relationship("User", backref="published_notices")

class EventGallery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id", ondelete="CASCADE"), nullable=False)
    image = db.Column(db.String(255), nullable=False)
    caption = db.Column(db.String(255))
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="pending")  # pending, approved, rejected
    moderated_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    moderated_at = db.Column(db.DateTime)
    rejection_reason = db.Column(db.Text)
    event = db.relationship("Event", backref="gallery")
    uploader = db.relationship("User", backref="uploaded_gallery", foreign_keys=[uploaded_by])
    moderator = db.relationship("User", backref="moderated_gallery", foreign_keys=[moderated_by])

class PastEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id", ondelete="CASCADE"), nullable=False, unique=True)
    archived_at = db.Column(db.DateTime, default=datetime.utcnow)
    archived_by = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"))
    highlights = db.Column(db.Text)
    results = db.Column(db.Text)
    documents_json = db.Column(db.JSON, default=list)
    event = db.relationship("Event", backref=db.backref("past_record", uselist=False))

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.context_processor
def inject_globals():
    unread = 0
    if current_user.is_authenticated:
        unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return {"college_name": COLLEGE, "college_short": SHORT, "unread_notifications": unread, "agc_profile": AGC_PROFILE, "agc_updates": AGC_UPDATES, "placeholder_image": url_for('static', filename='images/placeholder.svg')}


def image_url(path):
    """
    Resolve an image path to a usable URL.
    Handles absolute URLs (Cloudinary/S3) and relative static upload paths.
    Returns a placeholder image URL when path is empty or falsy.
    """
    if not path:
        return url_for('static', filename='images/placeholder.svg')
    if path.startswith(('http://', 'https://', '//')):
        return path
    return url_for('static', filename=path)


@app.template_filter('nl2br')
def nl2br_filter(text):
    """Convert newlines to <br> tags."""
    if not text:
        return ''
    from markupsafe import Markup, escape
    return Markup(escape(text).replace('\n', '<br>\n'))


def event_image_url(event):
    """Resolve an event's banner or image to a usable URL."""
    return image_url(event.banner or event.image)


app.jinja_env.globals['image_url'] = image_url
app.jinja_env.globals['event_image_url'] = event_image_url

def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def send_email(to, subject, body):
    server = os.getenv("MAIL_SERVER")
    username = os.getenv("MAIL_USERNAME")
    password = os.getenv("MAIL_PASSWORD")
    port = int(os.getenv("MAIL_PORT", "587"))
    use_tls = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
    if not server or not username or not password:
        print("\n--- CEMS EMAIL (development mode) ---")
        print("TO:", to)
        print("SUBJECT:", subject)
        print(body)
        print("--- END EMAIL ---\n")
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = username
        msg["To"] = to
        msg.set_content(body)
        with smtplib.SMTP(server, port) as smtp:
            if use_tls:
                smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(msg)
        return True
    except Exception as exc:
        print("SMTP error:", exc)
        return False
def create_notification(user_id, title, message):
    """Compatibility helper; route transactions commit notifications explicitly."""
    return notify(user_id, title, message)


def ensure_legacy_schema_compatibility():
    """Add new nullable columns to an existing development SQLite database.

    Flask-Migrate remains the production upgrade path. This compatibility step keeps
    the supplied one-command launcher usable when an older cems.db is already present.
    """
    db.create_all()
    additions = {
        "user": {
            "student_id": "VARCHAR(80)",
            "employee_id": "VARCHAR(80)",
            "profile_image": "VARCHAR(255)",
            "settings_json": "JSON",
            "last_login_at": "DATETIME",
        },
        "event": {
            "registration_start": "DATE",
            "published_at": "DATETIME",
            "updated_at": "DATETIME",
            "cancellation_reason": "TEXT",
            "results": "TEXT",
            "documents_json": "JSON",
            "custom_questions_json": "JSON",
            "contact_person": "VARCHAR(120)",
            "contact_email": "VARCHAR(160)",
            "contact_phone": "VARCHAR(30)",
        },
        "registration": {
            "terms_accepted": "BOOLEAN",
            "cancellation_reason": "TEXT",
            "cancelled_at": "DATETIME",
        },
        "notification": {
            "category": "VARCHAR(50)",
            "action_url": "VARCHAR(255)",
            "expires_at": "DATETIME",
        },
        "notice": {
            "attachment_name": "VARCHAR(255)",
            "expiry_date": "DATETIME",
            "updated_at": "DATETIME",
        },
        "event_gallery": {"caption": "VARCHAR(255)"},
        "event_waitlist": {"status": "VARCHAR(30)"},
        "attendance_record": {
            "status": "VARCHAR(30)",
            "scanned_by": "INTEGER",
        },
        "past_event": {
            "archived_by": "INTEGER",
            "highlights": "TEXT",
            "results": "TEXT",
            "documents_json": "JSON",
        },
    }
    inspector = sa_inspect(db.engine)
    with db.engine.begin() as connection:
        for table_name, columns in additions.items():
            if not inspector.has_table(table_name):
                continue
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    connection.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {column_type}'))


def seed_data():
    ensure_legacy_schema_compatibility()
    try:
        if User.query.count() == 0:
            admin = User(name="AGC Admin", email="admin@agc.local", role="admin", is_verified=True, department="Administration")
            admin.set_password("Admin@123")
            organizer = User(name="AGC Event Organizer", email="organizer@agc.local", role="organizer", is_verified=True, department="Student Affairs")
            organizer.set_password("Organizer@123")
            student = User(name="Rahul Sharma", email="student@agc.local", role="student", is_verified=True, department="Computer Science", roll_no="21CS1001", mobile="9876543210")
            student.set_password("Student@123")
            volunteer = User(name="Priya Volunteer", email="volunteer@agc.local", role="volunteer", is_verified=True, department="Student Affairs", mobile="9876543211")
            volunteer.set_password("Volunteer@123")
            teacher = User(name="Prof. Amit Kumar", email="teacher@agc.local", role="teacher", is_verified=True, department="Computer Science", mobile="9876543212")
            teacher.set_password("Teacher@123")
            db.session.add_all([admin, organizer, student, volunteer, teacher])
            db.session.flush()

            venues = [
                Venue(name="Main Auditorium", location="AGC Campus", capacity=500),
                Venue(name="Open Ground", location="AGC Campus", capacity=1000),
                Venue(name="Seminar Hall", location="Computer Science Block", capacity=250),
                Venue(name="Innovation Lab", location="Engineering Block", capacity=120),
            ]
            db.session.add_all(venues)
            db.session.flush()

            roles = [
                Role(name="student", description="Campus student"),
                Role(name="organizer", description="Event organizer"),
                Role(name="admin", description="Platform administrator"),
                Role(name="teacher", description="Faculty member"),
                Role(name="volunteer", description="Event volunteer"),
            ]
            db.session.add_all(roles)
            categories = [
                EventCategory(name="Academic", slug="academic", color="#7c3aed", sort_order=1),
                EventCategory(name="Technical", slug="technical", color="#e11d48", sort_order=2),
                EventCategory(name="Cultural", slug="cultural", color="#0891b2", sort_order=3),
                EventCategory(name="Sports", slug="sports", color="#16a34a", sort_order=4),
                EventCategory(name="Workshop", slug="workshop", color="#d97706", sort_order=5),
                EventCategory(name="Entrepreneurship", slug="entrepreneurship", color="#4f46e5", sort_order=6),
                EventCategory(name="Social", slug="social", color="#059669", sort_order=7),
            ]
            db.session.add_all(categories)
            db.session.add_all([
                AdminProfile(user_id=admin.id, employee_id="ADMIN-001", permissions_json=["*"]),
                OrganizerProfile(user_id=organizer.id, employee_id="ORG-001", title="Student Affairs Coordinator", department=organizer.department),
                StudentProfile(user_id=student.id, student_id="21CS1001", course="B.Tech Computer Science", semester="7"),
            ])
            db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    for user in User.query.all():
        if user.role == "student" and not StudentProfile.query.filter_by(user_id=user.id).first():
            db.session.add(StudentProfile(user_id=user.id, student_id=user.student_id or user.roll_no))
        elif user.role == "organizer" and not OrganizerProfile.query.filter_by(user_id=user.id).first():
            db.session.add(OrganizerProfile(user_id=user.id, employee_id=user.employee_id, department=user.department))
        elif user.role == "admin" and not AdminProfile.query.filter_by(user_id=user.id).first():
            db.session.add(AdminProfile(user_id=user.id, employee_id=user.employee_id, permissions_json=["*"]))
    db.session.commit()

    if Event.query.count() < 30:
        organizer = User.query.filter_by(role="organizer").first()
        if organizer:
            past_events = [
                ("Welcome Week - Freshers Party", "Cultural", "free", 2026, 1, 15, "10:00 AM", "4:00 PM", "Main Auditorium", 500, 0),
                ("Republic Day Celebration", "Cultural", "free", 2026, 1, 26, "9:00 AM", "12:00 PM", "Open Ground", 1000, 0),
                ("Science Exhibition 2026", "Academic", "free", 2026, 2, 10, "10:00 AM", "4:00 PM", "Seminar Hall", 300, 0),
                ("Holi Festival Celebration", "Cultural", "free", 2026, 3, 5, "11:00 AM", "5:00 PM", "Open Ground", 800, 0),
                ("Technical Symposium 2026", "Technical", "free", 2026, 3, 20, "9:00 AM", "5:00 PM", "Computer Lab", 200, 0),
                ("Blood Donation Camp", "Social", "free", 2026, 4, 12, "9:00 AM", "3:00 PM", "Health Center", 300, 0),
                ("Inter-College Sports Meet", "Sports", "free", 2026, 4, 25, "9:00 AM", "6:00 PM", "Sports Complex", 500, 0),
                ("Independence Day Special", "Cultural", "free", 2026, 8, 15, "8:00 AM", "11:00 AM", "Open Ground", 1000, 0),
            ]

            for title, cat, typ, y, m, d, st, et, venue, cap, fee in past_events:
                e = Event(title=title, category=cat, event_type=typ, date=datetime(y,m,d).date(),
                          start_time=st, end_time=et, venue=venue,
                          description=f"{title} was a campus event at {COLLEGE}.",
                          highlights="Student participation\nIndustry interaction\nCompetitions & activities\nNetworking & learning\nCertificates\nRefreshments",
                          capacity=cap, registration_deadline=datetime(y,m,d).date()-timedelta(days=2),
                          fee=fee, status="approved", organizer_id=organizer.id)
                db.session.add(e)
            db.session.flush()

            sample = [
                # Academic Events
                ("AI & Machine Learning Seminar", "Academic", "free", 2026, 9, 5, "10:00 AM", "12:00 PM", "Seminar Hall", 150, 0),
                ("Research Paper Writing Workshop", "Academic", "free", 2026, 9, 12, "2:00 PM", "4:00 PM", "Seminar Hall", 100, 0),
                ("NPTEL & Digital Learning Orientation", "Academic", "free", 2026, 9, 18, "11:00 AM", "1:00 PM", "Seminar Hall", 250, 0),
                ("Industrial Research Trends 2026", "Academic", "free", 2026, 9, 25, "10:00 AM", "2:00 PM", "Main Auditorium", 300, 0),
                ("Entrepreneurship & Innovation Lecture", "Academic", "paid", 2026, 10, 2, "3:00 PM", "5:00 PM", "Innovation Lab", 120, 99),
                ("PhD Scholars Research Colloquium", "Academic", "free", 2026, 10, 18, "10:00 AM", "4:00 PM", "Seminar Hall", 200, 0),
                ("International Conference on Engineering", "Academic", "paid", 2026, 11, 22, "9:00 AM", "5:00 PM", "Main Auditorium", 400, 149),
                ("Data Analytics for Beginners", "Academic", "free", 2026, 12, 5, "11:00 AM", "1:00 PM", "Computer Lab", 100, 0),
                
                # Technical Events
                ("AGC Tech Fest 2026", "Technical", "free", 2026, 9, 12, "10:00 AM", "5:00 PM", "Main Auditorium", 500, 0),
                ("Coding Hackathon - 24 Hours", "Technical", "free", 2026, 9, 28, "10:00 AM", "10:00 AM", "Innovation Lab", 200, 0),
                ("Web Development Bootcamp", "Technical", "paid", 2026, 10, 5, "9:00 AM", "5:00 PM", "Computer Lab", 80, 299),
                ("Mobile App Development Challenge", "Technical", "free", 2026, 10, 15, "2:00 PM", "6:00 PM", "Innovation Lab", 100, 0),
                ("Cybersecurity Workshop & Hands-on", "Technical", "paid", 2026, 10, 22, "10:00 AM", "4:00 PM", "Computer Lab", 60, 199),
                ("Cloud Computing Fundamentals", "Technical", "free", 2026, 11, 3, "11:00 AM", "1:00 PM", "Seminar Hall", 150, 0),
                ("Data Science & Analytics Masterclass", "Technical", "paid", 2026, 11, 10, "10:00 AM", "5:00 PM", "Computer Lab", 100, 249),
                ("Robotics & Automation Expo", "Technical", "free", 2026, 11, 28, "10:00 AM", "4:00 PM", "Innovation Lab", 250, 0),
                ("Blockchain & Web3 Workshop", "Technical", "paid", 2026, 12, 10, "2:00 PM", "6:00 PM", "Computer Lab", 80, 149),
                ("IoT Smart Devices Hackathon", "Technical", "free", 2026, 12, 20, "9:00 AM", "9:00 PM", "Computer Lab", 150, 0),
                
                # Cultural Events
                ("AGC Cultural Fiesta 2026", "Cultural", "free", 2026, 9, 19, "11:00 AM", "5:00 PM", "Open Ground", 1000, 0),
                ("Classical Music Concert", "Cultural", "free", 2026, 10, 8, "6:00 PM", "9:00 PM", "Main Auditorium", 500, 0),
                ("Contemporary Dance Performance", "Cultural", "free", 2026, 10, 16, "7:00 PM", "9:30 PM", "Open Ground", 800, 0),
                ("Art Exhibition & Painting Workshop", "Cultural", "free", 2026, 10, 24, "10:00 AM", "4:00 PM", "Innovation Lab", 200, 0),
                ("Theater & Dramatics Play", "Cultural", "free", 2026, 11, 5, "7:00 PM", "9:30 PM", "Main Auditorium", 600, 0),
                ("Poetry & Creative Writing Festival", "Cultural", "free", 2026, 11, 12, "5:00 PM", "8:00 PM", "Seminar Hall", 300, 0),
                ("Fashion Show - AGC Glamour Night", "Cultural", "paid", 2026, 11, 18, "6:00 PM", "10:00 PM", "Open Ground", 700, 99),
                ("Folk Dance & Music Evening", "Cultural", "free", 2026, 12, 1, "5:00 PM", "8:00 PM", "Main Auditorium", 400, 0),
                
                # Sports Events
                ("AGC Sports & Athletic Meet", "Sports", "free", 2026, 11, 7, "9:00 AM", "5:00 PM", "Open Ground", 1000, 0),
                ("Cricket Tournament Finals", "Sports", "free", 2026, 9, 20, "3:00 PM", "6:00 PM", "Open Ground", 500, 0),
                ("Football League Championship", "Sports", "free", 2026, 10, 12, "4:00 PM", "7:00 PM", "Open Ground", 800, 0),
                ("Badminton Singles & Doubles", "Sports", "free", 2026, 10, 28, "9:00 AM", "5:00 PM", "Sports Complex", 150, 0),
                ("Basketball 3-on-3 Tournament", "Sports", "free", 2026, 11, 14, "10:00 AM", "4:00 PM", "Sports Complex", 200, 0),
                ("Volleyball Championship", "Sports", "free", 2026, 11, 21, "3:00 PM", "7:00 PM", "Sports Complex", 250, 0),
                ("Chess & Carrom Championship", "Sports", "free", 2026, 12, 8, "10:00 AM", "4:00 PM", "Seminar Hall", 100, 0),
                ("Table Tennis Open Tournament", "Sports", "free", 2026, 12, 15, "9:00 AM", "5:00 PM", "Sports Complex", 120, 0),
                
                # Workshop Events
                ("AI & Emerging Technologies Workshop", "Workshop", "free", 2026, 10, 2, "10:00 AM", "2:00 PM", "Seminar Hall", 250, 0),
                ("Digital Marketing & Social Media", "Workshop", "paid", 2026, 10, 9, "2:00 PM", "5:00 PM", "Innovation Lab", 100, 149),
                ("Leadership & Team Management", "Workshop", "free", 2026, 10, 16, "10:00 AM", "1:00 PM", "Main Auditorium", 300, 0),
                ("Public Speaking & Presentation Skills", "Workshop", "free", 2026, 10, 23, "3:00 PM", "5:00 PM", "Seminar Hall", 200, 0),
                ("Graphic Design & UI/UX Basics", "Workshop", "paid", 2026, 11, 1, "10:00 AM", "4:00 PM", "Computer Lab", 80, 199),
                ("Environmental Awareness & Sustainability", "Workshop", "free", 2026, 11, 8, "2:00 PM", "4:00 PM", "Main Auditorium", 400, 0),
                ("Financial Literacy & Stock Market", "Workshop", "paid", 2026, 11, 20, "10:00 AM", "1:00 PM", "Seminar Hall", 200, 99),
                ("Photography & Videography Basics", "Workshop", "free", 2026, 12, 12, "10:00 AM", "3:00 PM", "Innovation Lab", 150, 0),
                
                # Entrepreneurship Events
                ("AGC Innovation & Entrepreneurship Summit", "Entrepreneurship", "paid", 2026, 10, 10, "10:00 AM", "4:00 PM", "Innovation Lab", 120, 199),
                ("Startup Pitch Competition", "Entrepreneurship", "free", 2026, 10, 25, "3:00 PM", "6:00 PM", "Main Auditorium", 500, 0),
                ("Business Model Canvas Workshop", "Entrepreneurship", "free", 2026, 11, 2, "10:00 AM", "12:30 PM", "Innovation Lab", 150, 0),
                ("Funding & Investor Pitching Session", "Entrepreneurship", "paid", 2026, 11, 9, "2:00 PM", "5:00 PM", "Innovation Lab", 100, 249),
                ("Social Enterprise & Impact Startup", "Entrepreneurship", "free", 2026, 11, 15, "11:00 AM", "1:00 PM", "Seminar Hall", 200, 0),
                ("Entrepreneurship Awareness Camp", "Entrepreneurship", "free", 2026, 12, 18, "10:00 AM", "3:00 PM", "Main Auditorium", 300, 0),
                ("Women Entrepreneurship Summit", "Entrepreneurship", "paid", 2026, 12, 22, "10:00 AM", "4:00 PM", "Innovation Lab", 100, 149),
            ]
            for title, cat, typ, y, m, d, st, et, venue, cap, fee in sample:
                e = Event(title=title, category=cat, event_type=typ, date=datetime(y,m,d).date(),
                          start_time=st, end_time=et, venue=venue,
                          description=f"{title} is a campus event at {COLLEGE}, designed for students, faculty, clubs and invited guests to learn, participate, collaborate and showcase talent. This event features industry experts, peer learning, and hands-on experience.",
                          highlights="Student participation\nIndustry interaction\nCompetitions & activities\nNetworking & learning\nCertificates\nRefreshments",
                          capacity=cap, registration_deadline=datetime(y,m,d).date()-timedelta(days=2),
                          fee=fee, status="approved", organizer_id=organizer.id)
                db.session.add(e)
            db.session.flush()

            event_cat_images = {
                "Academic": "https://res.cloudinary.com/demo/image/upload/v1700000000/cems/academic.jpg",
                "Technical": "https://res.cloudinary.com/demo/image/upload/v1700000000/cems/technical.jpg",
                "Cultural": "https://res.cloudinary.com/demo/image/upload/v1700000000/cems/cultural.jpg",
                "Sports": "https://res.cloudinary.com/demo/image/upload/v1700000000/cems/sports.jpg",
                "Workshop": "https://res.cloudinary.com/demo/image/upload/v1700000000/cems/workshop.jpg",
                "Entrepreneurship": "https://res.cloudinary.com/demo/image/upload/v1700000000/cems/entrepreneurship.jpg",
                "Social": "https://res.cloudinary.com/demo/image/upload/v1700000000/cems/community.jpg",
            }
            all_events = Event.query.filter(Event.image == None).all()
            for e in all_events:
                e.image = event_cat_images.get(e.category, "https://res.cloudinary.com/demo/image/upload/v1700000000/cems/event_default.jpg")
            db.session.commit()

    if Notice.query.count() == 0:
        admin = User.query.filter_by(role="admin").first()
        if admin:
            sample_notices = [
                ("AGC NEST 2026 Scholarship Applications Open",
                 "Applications are now open for the Amritsar Group of Colleges NEST 2026 scholarship program. Merit-based scholarships available for deserving students across all disciplines. Last date to apply: 15th September 2026. Apply online through the student portal.",
                 "Academic", "https://res.cloudinary.com/demo/image/upload/v1700000000/cems/notice_scholarship.jpg"),
                ("Revised Examination Date Sheet - November 2026",
                 "The revised date sheet for the November 2026 End Semester Examinations has been released. All affected students are advised to download the date sheet from the Examination portal and update their schedules accordingly.",
                 "Examination", "https://res.cloudinary.com/demo/image/upload/v1700000000/cems/notice_exam.jpg"),
                ("Campus Placements - Tech Mahindra Recruitment Drive",
                 "Tech Mahindra will conduct a campus recruitment drive for B.Tech final year students on 20th October 2026. Profile: Software Engineer. Package up to ₹7.5 LPA. Interested students must register on the placement portal by 18th October 2026.",
                 "Placement", "https://res.cloudinary.com/demo/image/upload/v1700000000/cems/notice_placement.jpg"),
                ("AGC Tech Fest 2026 - Registration Extended",
                 "Due to overwhelming response, registration for AGC Tech Fest 2026 has been extended until 15th September 2026. The event will feature hackathons, tech talks, and industry stalls. Don't miss out on this flagship technical event.",
                 "Technical", "https://res.cloudinary.com/demo/image/upload/v1700000000/cems/notice_techfest.jpg"),
                ("Blood Donation Camp - 12th November 2026",
                 "The NSS unit is organizing a voluntary blood donation camp on 12th November 2026 from 9:00 AM to 4:00 PM at the Health Center. All willing students, faculty, and staff are encouraged to participate and donate blood. Certificate of appreciation will be issued.",
                 "Social", "https://res.cloudinary.com/demo/image/upload/v1700000000/cems/notice_blood.jpg"),
                ("Library Timings - Extended for End Semester",
                 "In view of the upcoming end semester examinations, the Central Library will remain open from 7:00 AM to 11:00 PM daily until 30th November 2026. Students are advised to utilize the extended hours for exam preparation.",
                 "Academic", None),
                ("AGC Cultural Fiesta 2026 - Participants Required",
                 "The Annual AGC Cultural Fiesta will be held on 19th September 2026. Students interested in participating in music, dance, drama, and literary events can register their groups through the cultural portal by 10th September 2026.",
                 "Cultural", "https://res.cloudinary.com/demo/image/upload/v1700000000/cems/notice_cultural.jpg"),
            ]
            related_events = Event.query.filter_by(status="approved").all()
            notice_objs = []
            for i, (title, desc, category, img) in enumerate(sample_notices):
                related = related_events[i % len(related_events)] if related_events else None
                notice_objs.append(Notice(
                    title=title,
                    description=desc,
                    category=category,
                    event_id=related.id if related else None,
                    image=img,
                    published_by=admin.id,
                    status="published",
                    published_at=datetime.utcnow() - timedelta(days=len(sample_notices) - i)
                ))
            db.session.add_all(notice_objs)
            db.session.commit()
# ==============================
# AGC HOME
# ==============================

# ==============================
# ABOUT AGC
# ==============================

@app.route("/about")
def about():
    return render_template(
        "agc_info.html",
        info=AGC_INFO["about"]
    )


# ==============================
# CONTACT
# ==============================

@app.route("/contact")
def contact():
    return render_template(
        "contact.html"
    )


# ==============================
# AGC INFORMATION
# ==============================

@app.route("/agc-info/<slug>")
def agc_info(slug):

    if slug not in AGC_INFO:
        abort(404)

    return render_template(
        "agc_info.html",
        info=AGC_INFO[slug]
    )


# ==============================
# AGC MODULE
# ==============================

@app.route("/module/<slug>")
def agc_module(slug):
    if slug not in AGC_MODULES:
        abort(404)

    return render_template(
        "module.html",
        module=AGC_MODULES[slug]
    )


# ==============================
# NOTICE DETAILS
# ==============================

@app.route("/notice/<int:index>")
def notice_detail(index):

    if index < 0 or index >= len(AGC_NOTICES):
        abort(404)

    return render_template(
        "notice.html",
        notice=AGC_NOTICES[index]
    )
@app.route("/")
def landing():
    events = Event.query.filter_by(status="approved").order_by(Event.date.asc()).limit(4).all()
    return render_template("landing.html", events=events)

def validate_password_strength(password):
    """Validate password meets strength requirements: 8+ chars, letters, numbers, special chars."""
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if not re.search(r'[A-Za-z]', password):
        errors.append("Password must contain at least one letter (A-Z or a-z).")
    if not re.search(r'[0-9]', password):
        errors.append("Password must contain at least one number (0-9).")
    if not re.search(r'[^A-Za-z0-9]', password):
        errors.append("Password must contain at least one special character (!@#$%^&* etc.).")
    return errors


def validate_registration_payload(data):
    errors = {}
    name = clean_text(data.get("name", ""), 120)
    email = data.get("email", "").strip().lower()
    mobile = clean_text(data.get("mobile", ""), 20)
    password = data.get("password", "")
    confirm = data.get("confirm_password", "")
    role = data.get("role", "student")
    department = clean_text(data.get("department", ""), 100)
    student_id = clean_text(data.get("student_id", ""), 80)
    employee_id = clean_text(data.get("employee_id", ""), 80)
    course = clean_text(data.get("course", ""), 120)
    semester = clean_text(data.get("semester", ""), 30)

    if not name:
        errors["name"] = "Full name is required."
    if not email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        errors["email"] = "Enter a valid email address."
    if not password:
        errors["password"] = "Password is required."
    elif password != confirm:
        errors["confirm_password"] = "Passwords do not match."
    else:
        password_errors = validate_password_strength(password)
        if password_errors:
            errors["password"] = password_errors[0]
    if role not in ("student", "organizer"):
        errors["role"] = "Public registration is available for Students and Organizers only."
    if role == "student" and not student_id:
        errors["student_id"] = "Student ID is required."
    if role == "organizer" and not employee_id:
        errors["employee_id"] = "Employee/Organizer ID is required."
    if not errors:
        if User.query.filter_by(email=email).first():
            errors["email"] = "An account with this email already exists."
        if role == "student" and student_id and User.query.filter_by(student_id=student_id).first():
            errors["student_id"] = "This student ID is already registered."
        if role == "organizer" and employee_id and User.query.filter_by(employee_id=employee_id).first():
            errors["employee_id"] = "This organizer ID is already registered."
    return {
        "name": name,
        "email": email,
        "mobile": mobile,
        "password": password,
        "role": role,
        "department": department,
        "student_id": student_id,
        "employee_id": employee_id,
        "course": course,
        "semester": semester,
    }, errors


def persist_registration_user(data):
    profile_upload = request.files.get("profile_photo")
    profile_image = None
    if profile_upload and profile_upload.filename:
        profile_image = save_uploaded_file(profile_upload, "profiles", {"jpg", "jpeg", "png", "webp"}, 2 * 1024 * 1024, image=True)
    user = User(
        name=data["name"],
        email=data["email"],
        mobile=data["mobile"],
        role=data["role"],
        department=data["department"],
        student_id=data["student_id"] or None,
        employee_id=data["employee_id"] or None,
        course=data["course"] or None,
        semester=data["semester"] or None,
        profile_image=profile_image,
        is_verified=True,
        is_active_account=True,
    )
    user.set_password(data["password"])
    db.session.add(user)
    db.session.flush()
    if user.role == "student":
        db.session.add(StudentProfile(user_id=user.id, student_id=user.student_id, course=user.course, semester=user.semester))
    else:
        db.session.add(OrganizerProfile(user_id=user.id, employee_id=user.employee_id, department=user.department))
    db.session.commit()
    return user


@app.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        data, errors = validate_registration_payload(request.form)
        if errors:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "errors": errors}), 400
            for message in errors.values():
                flash(message, "danger")
            return render_template("auth/register.html", errors=errors)
        try:
            persist_registration_user(data)
        except (ValueError, OSError) as exc:
            db.session.rollback()
            errors = {"profile_photo": str(exc)}
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "errors": errors}), 400
            flash(errors["profile_photo"], "danger")
            return render_template("auth/register.html", errors=errors)
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": True, "message": "Account created successfully. You can now log in.", "redirect": url_for("login")})
        flash("Account created successfully. You can now log in.", "success")
        return redirect(url_for("login"))
    return render_template("auth/register.html", errors={})


@app.route("/api/register", methods=["POST"])
@limiter.limit("5 per hour")
def api_register():
    """AJAX registration endpoint used by integrations and legacy clients."""
    if current_user.is_authenticated:
        return jsonify({"success": False, "errors": {"general": "You are already logged in."}}), 400
    data, errors = validate_registration_payload(request.form)
    if errors:
        return jsonify({"success": False, "errors": errors}), 400
    try:
        persist_registration_user(data)
    except (ValueError, OSError) as exc:
        db.session.rollback()
        return jsonify({"success": False, "errors": {"profile_photo": str(exc)}}), 400
    return jsonify({"success": True, "message": "Account created successfully. You can now log in.", "redirect": url_for("login")})


@app.route("/api/login", methods=["POST"])
@limiter.limit("10 per minute")
def api_login():
    """AJAX login endpoint that returns JSON errors without full page refresh."""
    if current_user.is_authenticated:
        return jsonify({"success": True, "message": "Already logged in.", "redirect": url_for("dashboard")})
    email = request.form.get("email","").strip().lower()
    password = request.form.get("password","")
    selected_role = request.form.get("role", "student")
    errors = {}
    if not email:
        errors['email'] = "Please enter your email."
    if not password:
        errors['password'] = "Please enter your password."
    if not errors:
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            errors['credentials'] = "Invalid email or password."
        elif not user.is_active_account:
            errors['account'] = "Your account has been blocked by admin."
        elif user.role != selected_role:
            errors['role'] = f"This account does not belong to the selected {selected_role.title()} portal."
    if errors:
        return jsonify({"success": False, "errors": errors}), 400
    user.record_login()
    db.session.commit()
    login_user(user, remember=bool(request.form.get("remember")))
    return jsonify({"success": True, "message": "Login successful!", "redirect": url_for("dashboard")})


@app.route("/share/register")
def share_register():
    """Shareable registration form page."""
    return render_template("auth/share_register.html")


@app.route("/api/gallery/<int:gallery_id>/moderate", methods=["POST"])
@role_required("admin")
def moderate_gallery_image(gallery_id):
    """Admin endpoint to approve or reject a student-uploaded gallery image."""
    image = EventGallery.query.get_or_404(gallery_id)
    action = request.form.get("action","")
    if action == "approve":
        image.status = "approved"
        image.moderated_by = current_user.id
        image.moderated_at = datetime.utcnow()
        image.rejection_reason = None
        create_notification(image.uploaded_by, "Image Approved",
                            f"Your image for event '{image.event.title}' has been approved.")
    elif action == "reject":
        image.status = "rejected"
        image.moderated_by = current_user.id
        image.moderated_at = datetime.utcnow()
        image.rejection_reason = request.form.get("reason","")[:500] or "Does not meet content guidelines."
        create_notification(image.uploaded_by, "Image Rejected",
                            f"Your image for event '{image.event.title}' was rejected. Reason: {image.rejection_reason}")
    db.session.commit()
    return jsonify({"success": True, "status": image.status})


@app.route("/api/gallery/<int:gallery_id>/upload", methods=["POST"])
@role_required("student")
def api_upload_gallery_image(gallery_id):
    """AJAX upload endpoint for student event images with validation."""
    event = Event.query.get_or_404(gallery_id)
    if event.status != "approved":
        return jsonify({"success": False, "errors": {"general": "This event is not approved yet."}}), 403
    reg = Registration.query.filter_by(user_id=current_user.id, event_id=event.id).first()
    if not reg:
        return jsonify({"success": False, "errors": {"general": "You must be registered for this event to upload images."}}), 403
    image = request.files.get("image")
    if not image or not image.filename:
        return jsonify({"success": False, "errors": {"image": "Please select a valid image."}}), 400
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if image.mimetype not in allowed:
        return jsonify({"success": False, "errors": {"image": "Only JPG, PNG, and WEBP images are allowed."}}), 400
    image.seek(0, 2)
    size = image.tell()
    image.seek(0)
    if size > 4 * 1024 * 1024:
        return jsonify({"success": False, "errors": {"image": "Image size must be less than 4MB."}}), 400
    import os
    from werkzeug.utils import secure_filename
    os.makedirs("static/uploads/gallery", exist_ok=True)
    ext = image.filename.rsplit(".", 1)[-1].lower() if "." in image.filename else "jpg"
    safe_name = secure_filename(image.filename).rsplit(".", 1)[0] or "image"
    path = f"uploads/gallery/{event.id}_{current_user.id}_{secrets.token_hex(4)}.{ext}"
    image.save(os.path.join("static", path))
    gallery = EventGallery(
        event_id=event.id,
        image=path,
        uploaded_by=current_user.id,
        status="pending"
    )
    db.session.add(gallery)
    db.session.commit()
    return jsonify({"success": True, "message": "Image submitted for admin approval.", "gallery_id": gallery.id})


@app.route("/api/events/<int:event_id>/register", methods=["POST"])
@role_required("student")
def api_register_event(event_id):
    """AJAX free-event registration endpoint with atomic backend validation."""
    event = Event.query.get_or_404(event_id)
    try:
        registration = register_student(
            event,
            current_user._get_current_object(),
            terms_accepted=request.form.get("terms_accepted") in {"on", "true", "1"},
        )
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"success": False, "errors": {"registration": str(exc)}}), 400
    return jsonify({
        "success": True,
        "message": "You have successfully registered for this event.",
        "ticket_code": registration.ticket_code,
        "registration_id": registration.id,
    })


@app.route("/api/profile/update", methods=["POST"])
@role_required("student")
def api_update_profile():
    """AJAX profile update endpoint."""
    name = request.form.get("name","").strip()
    mobile = request.form.get("mobile","").strip()
    department = request.form.get("department","").strip()
    roll_no = request.form.get("roll_no","").strip()
    course = request.form.get("course","").strip()
    semester = request.form.get("semester","").strip()
    errors = {}
    if not name:
        errors['name'] = "Name is required."
    if errors:
        return jsonify({"success": False, "errors": errors}), 400
    current_user.name = name
    current_user.mobile = mobile
    current_user.department = department
    current_user.roll_no = roll_no
    current_user.course = course
    current_user.semester = semester
    db.session.commit()
    return jsonify({"success": True, "message": "Profile updated successfully."})

@app.route("/verify/<token>")
def verify_email(token):
    user = User.query.filter_by(verification_token=token).first_or_404()
    user.is_verified = True
    user.verification_token = None
    db.session.commit()
    flash("Email verified successfully. You can now log in.", "success")
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    selected_role = request.args.get("role", "student")
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        # Read role from POST form data, falling back to query param
        selected_role = request.form.get("role", selected_role)
        if selected_role not in ("student", "organizer", "admin"):
            selected_role = "student"
        errors = {}
        if not email:
            errors['email'] = "Please enter your email."
        if not password:
            errors['password'] = "Please enter your password."
        if not errors:
            user = User.query.filter_by(email=email).first()
            if not user or not user.check_password(password):
                errors['credentials'] = "Invalid email or password."
            elif not user.is_active_account:
                errors['account'] = "Your account has been blocked by admin."
            elif user.role != selected_role:
                role_labels = {"student": "Student", "organizer": "Organizer", "admin": "Admin"}
                errors['role'] = f"This account is not registered as a {role_labels.get(selected_role, selected_role)}."
        if errors:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"success": False, "errors": errors}), 400
            for field, msg in errors.items():
                flash(msg, "danger")
            return render_template("auth/login.html", errors=errors, selected_role=selected_role)
        user.record_login()
        db.session.commit()
        login_user(user, remember=bool(request.form.get("remember")))
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": True, "message": "Login successful!", "redirect": url_for("dashboard")})
        return redirect(url_for("dashboard"))
    return render_template("auth/login.html", errors={}, selected_role=selected_role)

@app.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            db.session.commit()
            reset_url = url_for("reset_password", token=token, _external=True)
            send_email(email, "CEMS password reset", f"Reset your password:\n{reset_url}")
        flash("If the account exists, a reset link has been generated.", "info")
        return redirect(url_for("login"))
    return render_template("auth/forgot.html")

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first_or_404()
    if request.method == "POST":
        password = request.form.get("password","")
        confirm = request.form.get("confirm_password","")
        if len(password) < 8 or password != confirm:
            flash("Use matching passwords of at least 8 characters.", "danger")
        else:
            user.set_password(password)
            user.reset_token = None
            db.session.commit()
            flash("Password updated. Please log in.", "success")
            return redirect(url_for("login"))
    return render_template("auth/reset.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("landing"))

@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == "admin":
        return redirect(url_for("admin_dashboard"))
    if current_user.role == "organizer":
        return redirect(url_for("organizer_dashboard"))
    if current_user.role == "volunteer":
        return redirect(url_for("volunteer_dashboard"))
    if current_user.role == "teacher":
        return redirect(url_for("teacher_dashboard"))
    return redirect(url_for("student_dashboard"))

@app.route("/events")
def events():
    q = request.args.get("q","").strip()
    category = request.args.get("category","").strip()
    status = request.args.get("status","").strip()
    page = request.args.get("page", 1, type=int)
    query = Event.query.filter(Event.status.in_(["approved", "published"]))
    if q:
        query = query.filter(Event.title.ilike(f"%{q}%"))
    if category:
        query = query.filter_by(category=category)
    today = datetime.utcnow().date()
    # Students should only see upcoming events for registration
    is_student = current_user.is_authenticated and current_user.role == "student"
    if is_student:
        query = query.filter(Event.date >= today)
    else:
        if status == "upcoming":
            query = query.filter(Event.date >= today)
        elif status == "completed":
            query = query.filter(Event.date < today)
    pagination = query.order_by(Event.date.asc()).paginate(page=page, per_page=12, error_out=False)
    categories = [r[0] for r in db.session.query(Event.category).distinct().all()]
    return render_template("events.html", events=pagination.items, categories=categories, q=q, category=category, status=status, pagination=pagination, is_student=is_student)

@app.route("/events/<int:event_id>")
def event_details(event_id):
    event = Event.query.get_or_404(event_id)
    if event.status not in ("approved", "published"):
        if not current_user.is_authenticated or current_user.role not in ("admin", "organizer") or (current_user.role == "organizer" and event.organizer_id != current_user.id):
            abort(404)
    registered = False
    if current_user.is_authenticated:
        registered = Registration.query.filter(
            Registration.user_id == current_user.id,
            Registration.event_id == event.id,
            Registration.status != "cancelled",
        ).first() is not None
    seats = available_seats(event)
    return render_template("event_details.html", event=event, registered=registered, seats=max(seats,0))

@app.route("/student/dashboard")
@role_required("student")
def student_dashboard():
    upcoming = Event.query.filter(Event.status=="approved", Event.date >= datetime.utcnow().date()).order_by(Event.date).limit(4).all()
    past_events = Event.query.join(PastEvent, Event.id == PastEvent.event_id).filter(Event.status=="approved").order_by(Event.date.desc()).limit(4).all()
    regs = Registration.query.filter_by(user_id=current_user.id).count()
    attended = Registration.query.filter_by(user_id=current_user.id, attended=True).count()
    tickets = Registration.query.filter_by(user_id=current_user.id, status="confirmed").count()
    notices = Notice.query.filter_by(status="published").count()
    uploaded_images = EventGallery.query.filter_by(uploaded_by=current_user.id).count()
    return render_template("student/dashboard.html", upcoming=upcoming, past_events=past_events, regs=regs, attended=attended, tickets=tickets, notices=notices, uploaded_images=uploaded_images)

@app.route("/volunteer/dashboard")
@role_required("volunteer")
def volunteer_dashboard():
    return render_template("volunteer/dashboard.html")

@app.route("/teacher/dashboard")
@role_required("teacher")
def teacher_dashboard():
    return render_template("teacher/dashboard.html")

@app.route("/events/<int:event_id>/register", methods=["GET","POST"])
@role_required("student")
def register_event(event_id):
    event = Event.query.get_or_404(event_id)
    if event.status != "approved":
        flash("This event is not available for registration.", "danger")
        return redirect(url_for("events"))
    existing = Registration.query.filter_by(user_id=current_user.id, event_id=event.id).first()
    if existing:
        flash("You are already registered for this event.", "info")
        return redirect(url_for("my_registrations"))
    if request.method == "POST":
        if event.fee > 0:
            terms_accepted = request.form.get("terms_accepted") == "on"
            if not terms_accepted:
                flash("Please accept the event terms before continuing to payment.", "warning")
                return redirect(url_for("register_event", event_id=event.id))
            registration = Registration(
                ticket_code="AGC-" + secrets.token_hex(6).upper(),
                user_id=current_user.id,
                event_id=event.id,
                status="pending",
                payment_status="pending",
                terms_accepted=True,
            )
            db.session.add(registration)
            db.session.flush()
            db.session.add(Ticket(registration_id=registration.id, qr_token=secrets.token_urlsafe(32), status="active"))
            db.session.commit()
            return redirect(url_for("demo_payment", event_id=event.id, registration_id=registration.id))
        try:
            registration = register_student(
                event,
                current_user._get_current_object(),
                terms_accepted=request.form.get("terms_accepted") == "on",
            )
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return redirect(url_for("event_details", event_id=event.id))
        flash("Registration successful. Your digital ticket is ready.", "success")
        return redirect(url_for("ticket", registration_id=registration.id))
    return render_template("student/register_event.html", event=event, terms_required=True)

@app.route("/student/registrations")
@role_required("student")
def my_registrations():
    regs = Registration.query.filter_by(user_id=current_user.id).order_by(Registration.registered_at.desc()).all()
    return render_template("student/registrations.html", registrations=regs)

@app.route("/student/tickets")
@role_required("student")
def my_tickets():
    regs = Registration.query.filter_by(user_id=current_user.id, status="confirmed").order_by(Registration.registered_at.desc()).all()
    return render_template("student/tickets.html", registrations=regs)

@app.route("/ticket/<int:registration_id>")
@login_required
def ticket(registration_id):
    reg = Registration.query.get_or_404(registration_id)
    if reg.user_id != current_user.id and current_user.role not in ("admin","organizer"):
        abort(403)
    return render_template("student/ticket.html", reg=reg)

@app.route("/ticket/<int:registration_id>/qr")
@login_required
def ticket_qr(registration_id):
    reg = Registration.query.get_or_404(registration_id)
    if reg.user_id != current_user.id and current_user.role not in ("admin","organizer"):
        abort(403)
    ticket = ensure_ticket(reg)
    img = qrcode.make(ticket.qr_token)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png", download_name=f"{reg.ticket_code}.png")

@app.route("/ticket/<int:registration_id>/download")
@login_required
def ticket_download(registration_id):
    from reportlab.lib.colors import Color, HexColor
    from reportlab.lib.units import mm
    reg = Registration.query.get_or_404(registration_id)
    if reg.user_id != current_user.id and current_user.role not in ("admin","organizer"):
        abort(403)

    primary = HexColor("#6366f1")
    dark = HexColor("#1e293b")
    light = HexColor("#f1f5f9")
    white = HexColor("#ffffff")
    accent = HexColor("#10b981")

    ticket = ensure_ticket(reg)
    qr_img = qrcode.make(ticket.qr_token)
    qr_buf = BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, pageCompression=0)
    w, h = A4
    c.setTitle(f"Ticket - {reg.ticket_code}")

    c.setFillColor(white)
    c.rect(20, 20, w-40, h-40, fill=1, stroke=0)

    c.setFillColor(primary)
    c.rect(20, h-70, w-40, 70, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(40, h-50, "CEMS DIGITAL ENTRY TICKET")

    c.setFillColor(dark)
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(w/2, h-170, reg.event.title.upper())

    c.setFillColor(primary)
    c.setLineWidth(3)
    c.rect(80, h-210, w-160, 1, fill=1, stroke=0)

    c.setFillColor(dark)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(80, h-250, "Event Details")
    c.setFont("Helvetica", 12)
    y = h - 280
    detail_lines = [
        ("Date", reg.event.date.strftime('%A, %d %B %Y')),
        ("Time", f"{reg.event.start_time} - {reg.event.end_time}"),
        ("Venue", reg.event.venue),
        ("Category", reg.event.category),
        ("Participant", reg.user.name),
        ("Email", reg.user.email),
        ("Roll No", reg.user.roll_no or "—"),
        ("Department", reg.user.department or "—"),
        ("Ticket ID", reg.ticket_code),
        ("Payment", reg.payment_status.title()),
    ]
    c.setFillColor(dark)
    for label, value in detail_lines:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(80, y, f"{label}:")
        c.setFont("Helvetica", 11)
        c.drawString(180, y, str(value))
        y -= 22

    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(qr_buf), w - 220, h - 310, width=140, height=140, mask='auto')

    c.setFillColor(accent)
    c.setStrokeColor(accent)
    c.setLineWidth(2)
    c.rect(w - 220, h - 340, 140, 40, fill=1)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(w - 150, h - 320, "VERIFIED")
    c.drawCentredString(w - 150, h - 335, "ENTRY")

    c.setFillColor(dark)
    c.setStrokeColor(light)
    c.setLineWidth(1)
    c.rect(80, 120, w-160, 1, fill=0)

    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor("#64748b"))
    c.drawCentredString(w/2, 95, f"Ticket Code: {reg.ticket_code} | Generated by CEMS")
    c.drawCentredString(w/2, 75, f"Status: {'Attended' if reg.attended else 'Registered'}")
    c.drawCentredString(w/2, 55, "This ticket is valid for single entry. Please bring valid ID.")

    c.setFillColor(dark)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(w/2, 30, f"{COLLEGE} — {SHORT} Campus Event Management System")
    c.save()
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=f"ticket-{reg.ticket_code}.pdf")

@app.route("/student/notifications")
@role_required("student")
def student_notifications():
    notes = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    for n in notes:
        n.is_read = True
    db.session.commit()
    return render_template("student/notifications.html", notifications=notes)

@app.route("/profile", methods=["GET", "POST"])
@role_required("student")
def profile():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        mobile = request.form.get("mobile","").strip()
        department = request.form.get("department","").strip()
        roll_no = request.form.get("roll_no","").strip()
        course = request.form.get("course","").strip()
        semester = request.form.get("semester","").strip()
        errors = {}
        if not name:
            errors['name'] = "Name is required."
        if errors:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"success": False, "errors": errors}), 400
            for field, msg in errors.items():
                flash(msg, "danger")
            return render_template("student/profile.html", errors=errors)
        current_user.name = name
        current_user.mobile = mobile
        current_user.department = department
        current_user.roll_no = roll_no
        current_user.course = course
        current_user.semester = semester
        db.session.commit()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": True, "message": "Profile updated successfully."})
        flash("Profile updated successfully.", "success")
        return redirect(url_for("profile"))
    return render_template("student/profile.html", errors={})

@app.route("/registration/<int:registration_id>/feedback", methods=["POST"])
@role_required("student")
def feedback(registration_id):
    reg = Registration.query.get_or_404(registration_id)
    if reg.user_id != current_user.id:
        abort(403)
    rating = int(request.form.get("rating", 5))
    rating = min(max(rating,1),5)
    db.session.add(Feedback(registration_id=reg.id, rating=rating, comment=request.form.get("comment","")))
    db.session.commit()
    flash("Thank you for your feedback.", "success")
    return redirect(url_for("my_registrations"))

@app.route("/organizer/dashboard")
@role_required("organizer")
def organizer_dashboard():
    evs = Event.query.filter_by(organizer_id=current_user.id).order_by(Event.date.desc()).all()
    total_reg = sum(len(e.registrations) for e in evs)
    total_att = sum(1 for e in evs for r in e.registrations if r.attended)
    revenue = sum(e.fee * len([r for r in e.registrations if r.payment_status in {"paid", "successful"}]) for e in evs)
    pending = sum(1 for e in evs if e.status in ("pending", "submitted"))
    approved = sum(1 for e in evs if e.status == "approved")
    rejected = sum(1 for e in evs if e.status == "rejected")
    change_pending = sum(1 for e in evs if e.change_status == "pending")
    return render_template("organizer/dashboard.html", events=evs, total_reg=total_reg, total_att=total_att, revenue=revenue,
                           pending=pending, approved=approved, rejected=rejected, change_pending=change_pending)

@app.route("/organizer/festival-calendar")
@role_required("organizer")
def festival_calendar():
    year = request.args.get("year", datetime.utcnow().year, type=int)
    festivals = [
        {"name": "Republic Day", "date": datetime(year, 1, 26).date(), "type": "National"},
        {"name": "Holi", "date": datetime(year, 3, 14).date(), "type": "Festival"},
        {"name": "Diwali", "date": datetime(year, 10, 20).date(), "type": "Festival"},
        {"name": "Independence Day", "date": datetime(year, 8, 15).date(), "type": "National"},
        {"name": "Gandhi Jayanti", "date": datetime(year, 10, 2).date(), "type": "National"},
        {"name": "Christmas", "date": datetime(year, 12, 25).date(), "type": "Festival"},
        {"name": "Eid al-Fitr", "date": datetime(year, 3, 30).date(), "type": "Festival"},
        {"name": "Ganesh Chaturthi", "date": datetime(year, 9, 7).date(), "type": "Festival"},
        {"name": "Navratri", "date": datetime(year, 10, 3).date(), "type": "Festival"},
        {"name": "Dussehra", "date": datetime(year, 10, 12).date(), "type": "Festival"},
    ]
    return render_template("organizer/festival_calendar.html", festivals=festivals, year=year)

@app.route("/organizer/events/create", methods=["GET","POST"])
@role_required("organizer")
def create_event():
    if request.method == "POST":
        data = request.form.to_dict()
        normalized, errors = validate_event_payload(data)
        if errors:
            messages = [message for message in errors.values() for _ in range(1)]
            for message in messages:
                flash(message, "danger")
            return render_template("organizer/create_event.html", errors=errors), 400

        action = request.form.get("action", "draft")
        status = "pending" if action == "submit" else "draft"
        conflicts = Event.query.filter(
            Event.venue == normalized["venue"],
            Event.date == normalized["date"],
            Event.status.in_(["approved", "waiting"]),
        ).all()
        event_start = parse_time(normalized["start_time"])
        event_end = parse_time(normalized["end_time"])
        for conflict in conflicts:
            conflict_start = parse_time(conflict.start_time)
            conflict_end = parse_time(conflict.end_time)
            if conflict_start and conflict_end and event_start < conflict_end and conflict_start < event_end:
                flash(f"Venue conflict: {normalized['venue']} is already booked for {conflict.title} ({conflict.start_time}-{conflict.end_time}).", "danger")
                return render_template("organizer/create_event.html", errors={"venue": "Choose another venue or time."}), 409

        event = Event(
            title=normalized["title"],
            category=normalized["category"],
            event_type=normalized["event_type"],
            date=normalized["date"],
            start_time=normalized["start_time"],
            end_time=normalized["end_time"],
            venue=normalized["venue"],
            description=clean_text(data.get("description", ""), 10000),
            highlights=clean_text(data.get("highlights", ""), 5000),
            rules=clean_text(data.get("rules", ""), 5000),
            eligibility=clean_text(data.get("eligibility", ""), 5000),
            contact_info=clean_text(data.get("contact_info", ""), 1000),
            main_guest=clean_text(data.get("main_guest", ""), 120) or None,
            chief_guest=clean_text(data.get("chief_guest", ""), 120) or None,
            capacity=normalized["capacity"],
            registration_start=normalized["registration_start"],
            registration_deadline=normalized["registration_deadline"],
            fee=normalized["fee"],
            status=status,
            organizer_id=current_user.id,
            custom_questions_json=parse_custom_questions(data.get("custom_questions", "")),
        )
        db.session.add(event)
        db.session.flush()
        try:
            banner = request.files.get("banner")
            if banner and banner.filename:
                event.image = save_uploaded_file(
                    banner,
                    "banners",
                    {"jpg", "jpeg", "png", "webp"},
                    4 * 1024 * 1024,
                    image=True,
                )
            db.session.commit()
            audit(current_user, "event.created", "Event", event.id, f"{current_user.name} created {event.title}.")
            if status == "pending":
                create_notification(current_user.id, "Event submitted", f"{event.title} was submitted for admin review.")
                flash("Event submitted for admin approval.", "success")
            else:
                flash("Event saved as draft.", "success")
            return redirect(url_for("organizer_dashboard"))
        except (ValueError, OSError) as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return render_template("organizer/create_event.html", errors={"banner": str(exc)}), 400
    return render_template("organizer/create_event.html", errors={})

@app.route("/organizer/events/<int:event_id>/manage", methods=["GET","POST"])
@role_required("organizer")
def manage_event(event_id):
    event = Event.query.get_or_404(event_id)
    if event.organizer_id != current_user.id:
        abort(403)
    if request.method == "POST":
        important_fields = {"date", "start_time", "end_time", "venue", "capacity", "registration_deadline"}
        changed_important = any(
            request.form.get(field) != str(getattr(event, field))
            for field in important_fields
            if hasattr(event, field)
        )
        if event.status == "approved" and changed_important:
            event.original_data = {
                "date": str(event.date),
                "start_time": event.start_time,
                "end_time": event.end_time,
                "venue": event.venue,
                "capacity": event.capacity,
                "registration_deadline": str(event.registration_deadline) if event.registration_deadline else None,
            }
            event.date = datetime.strptime(request.form.get("date"), "%Y-%m-%d").date()
            event.start_time = request.form.get("start_time", event.start_time).strip()
            event.end_time = request.form.get("end_time", event.end_time).strip()
            event.venue = request.form.get("venue", event.venue).strip()
            event.capacity = int(request.form.get("capacity", event.capacity))
            event.registration_deadline = datetime.strptime(request.form.get("registration_deadline"), "%Y-%m-%d").date() if request.form.get("registration_deadline") else None
            event.change_status = "pending"
            event.status = "waiting"
            create_notification(current_user.id, "Change pending approval", f"Changes to {event.title} require admin approval.")
            flash("Important changes submitted for admin approval.", "success")
        else:
            event.title = request.form.get("title", event.title).strip()
            event.category = request.form.get("category", event.category).strip()
            event.event_type = request.form.get("event_type", event.event_type).strip()
            event.venue = request.form.get("venue", event.venue).strip()
            event.description = request.form.get("description", event.description).strip()
            event.highlights = request.form.get("highlights", event.highlights).strip()
            event.rules = request.form.get("rules", event.rules).strip()
            event.eligibility = request.form.get("eligibility", event.eligibility).strip()
            event.contact_info = request.form.get("contact_info", event.contact_info).strip()
            event.main_guest = request.form.get("main_guest", event.main_guest).strip() or None
            event.chief_guest = request.form.get("chief_guest", event.chief_guest).strip() or None
            event.capacity = int(request.form.get("capacity", event.capacity))
            event.registration_deadline = datetime.strptime(request.form.get("registration_deadline"), "%Y-%m-%d").date() if request.form.get("registration_deadline") else None
            event.custom_questions_json = parse_custom_questions(request.form.get("custom_questions", ""))
            if event.status in ("rejected", "draft"):
                event.status = "pending"
                create_notification(current_user.id, "Event resubmitted", f"{event.title} was resubmitted for admin review.")
        banner = request.files.get("banner")
        if banner and banner.filename:
            try:
                event.image = save_uploaded_file(banner, "banners", {"jpg", "jpeg", "png", "webp"}, 4 * 1024 * 1024, image=True)
            except (ValueError, OSError) as exc:
                db.session.rollback()
                flash(str(exc), "danger")
                return render_template("organizer/manage_event.html", event=event, errors={"banner": str(exc)}), 400
        db.session.commit()
        audit(current_user, "event.updated", "Event", event.id, f"{current_user.name} updated {event.title}.")
        flash("Event updated.", "success")
    return render_template("organizer/manage_event.html", event=event)

@app.route("/organizer/events/<int:event_id>/registrations")
@role_required("organizer")
def organizer_registrations(event_id):
    event = Event.query.get_or_404(event_id)
    if event.organizer_id != current_user.id:
        abort(403)
    registrations = Registration.query.filter_by(event_id=event.id).order_by(Registration.registered_at.desc()).all()
    return render_template("organizer/registrations.html", event=event, registrations=registrations)

@app.route("/organizer/checkin", methods=["GET","POST"])
@role_required("organizer")
def checkin():
    result = None
    if request.method == "POST":
        code = request.form.get("ticket_code","").strip()
        if not code:
            flash("Enter a ticket code or scan a QR code.", "danger")
        else:
            try:
                result, already_attended = mark_attendance(code, current_user._get_current_object())
            except LookupError:
                flash("Ticket not found.", "danger")
            except PermissionError:
                flash("This ticket belongs to another organizer.", "danger")
            except ValueError as exc:
                flash(str(exc), "danger")
            else:
                flash("Already checked in." if already_attended else f"{result.user.name} checked in successfully.",
                      "warning" if already_attended else "success")
    return render_template("organizer/checkin.html", result=result)

@app.route("/organizer/checkin/scan")
@role_required("organizer")
def qr_scanner():
    return render_template("organizer/qr_scanner.html")

@app.route("/api/checkin", methods=["POST"])
@role_required("organizer")
def api_checkin():
    """
    API endpoint for QR-code-based check-in.
    Accepts JSON { "ticket_code": "AGC-XXXX" } and marks attendance.
    Returns JSON with result status and participant info.
    """
    data = request.get_json(silent=True) or {}
    if not data:
        data = request.form.to_dict()
    identifier = data.get("qr_token") or data.get("ticket_code")
    if not identifier:
        return {"success": False, "message": "No ticket code or QR token provided."}, 400
    try:
        reg, already_attended = mark_attendance(identifier, current_user._get_current_object())
    except LookupError:
        return {"success": False, "message": "Ticket not found."}, 404
    except PermissionError:
        return {"success": False, "message": "This ticket belongs to another event organizer."}, 403
    except ValueError as exc:
        return {"success": False, "message": str(exc)}, 400
    return {
        "success": True,
        "already_attended": already_attended,
        "message": "Already checked in." if already_attended else f"{reg.user.name} checked in successfully.",
        "participant": reg.user.name,
        "event": reg.event.title,
        "ticket_code": reg.ticket_code,
        "checkin_time": reg.checkin_time.strftime('%d %b %Y %I:%M %p') if reg.checkin_time else None,
    }

@app.route("/organizer/events/<int:event_id>/certificates")
@role_required("organizer")
def generate_certificates(event_id):
    event = Event.query.get_or_404(event_id)
    if event.organizer_id != current_user.id:
        abort(403)
    attended_regs = Registration.query.filter_by(event_id=event.id, attended=True).all()
    issued = 0
    for reg in attended_regs:
        if not DigitalCertificate.query.filter_by(registration_id=reg.id).first():
            cert = DigitalCertificate(
                registration_id=reg.id,
                certificate_code=reg.ticket_code,
                achievement=f"Participation in {event.title}",
                issued_date=datetime.utcnow(),
                verified=True,
                verification_code=secrets.token_urlsafe(16)
            )
            db.session.add(cert)
            issued += 1
    db.session.commit()
    flash(f"{issued} certificate(s) generated for attended participants.", "success")
    return redirect(url_for("organizer_registrations", event_id=event.id))

@app.route("/organizer/reports")
@role_required("organizer")
def organizer_reports():
    events = Event.query.filter_by(organizer_id=current_user.id).all()
    total_events = len(events)
    total_reg = sum(len(e.registrations) for e in events)
    total_att = sum(1 for e in events for r in e.registrations if r.attended)
    revenue = sum(e.fee * sum(1 for r in e.registrations if r.payment_status in {"paid", "successful"}) for e in events)
    return render_template("organizer/reports.html", events=events, total_events=total_events,
                           total_reg=total_reg, total_att=total_att, revenue=revenue)


@app.route("/payment/<int:event_id>", methods=["GET","POST"])
@role_required("student")
def demo_payment(event_id):
    event = Event.query.get_or_404(event_id)
    if event.fee <= 0:
        return redirect(url_for("register_event", event_id=event.id))
    requested_id = request.args.get("registration_id", type=int)
    registration = Registration.query.filter_by(
        user_id=current_user.id,
        event_id=event.id,
    ).order_by(Registration.registered_at.desc()).first()
    if registration and registration.status == "confirmed" and registration.payment_status in {"paid", "successful"}:
        return redirect(url_for("ticket", registration_id=registration.id))
    if not registration or (requested_id is not None and registration.id != requested_id) or registration.status != "pending":
        registration = Registration(
            ticket_code="AGC-" + secrets.token_hex(6).upper(),
            user_id=current_user.id,
            event_id=event.id,
            status="pending",
            payment_status="pending",
            terms_accepted=True,
        )
        db.session.add(registration)
        db.session.flush()
        db.session.add(Ticket(registration_id=registration.id, qr_token=secrets.token_urlsafe(32), status="active"))
        db.session.commit()
    if request.method == "POST":
        payment_method = request.form.get("payment_method", "mock").lower()
        if payment_method not in {"mock", "card", "upi", "netbanking", "wallet", "cash"}:
            flash("Select a supported demo payment method.", "danger")
            return redirect(url_for("demo_payment", event_id=event.id, registration_id=registration.id))
        try:
            create_mock_payment(registration, payment_method=payment_method)
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return redirect(url_for("demo_payment", event_id=event.id, registration_id=registration.id))
        flash("Demo payment successful. Your ticket has been generated.", "success")
        return redirect(url_for("ticket", registration_id=registration.id))
    return render_template("student/payment.html", event=event, registration=registration)


@app.route("/events/<int:event_id>/upload-image", methods=["POST"])
@role_required("student")
def upload_event_image(event_id):
    """Allow a registered student to upload event photos for admin-approved events."""
    event = Event.query.get_or_404(event_id)
    if event.status != "approved":
        flash("This event is not approved yet.", "danger")
        return redirect(url_for("event_details", event_id=event.id))
    reg = Registration.query.filter_by(user_id=current_user.id, event_id=event.id).first()
    if not reg:
        flash("You must be registered for this event to upload images.", "danger")
        return redirect(url_for("event_details", event_id=event.id))
    images = request.files.getlist("images")
    if not images or not images[0].filename:
        flash("No images selected for upload.", "danger")
        return redirect(url_for("event_details", event_id=event.id))
    import os
    from werkzeug.utils import secure_filename
    os.makedirs("static/uploads/gallery", exist_ok=True)
    uploaded = 0
    for image in images:
        if image and image.filename:
            filename = secure_filename(image.filename)
            path = f"uploads/gallery/{event_id}_{current_user.id}_{filename}"
            image.save(os.path.join("static", path))
            db.session.add(EventGallery(
                event_id=event_id,
                image=path,
                uploaded_by=current_user.id
            ))
            uploaded += 1
    db.session.commit()
    flash(f"{uploaded} image(s) uploaded successfully. They will be visible to all students.", "success")
    return redirect(url_for("event_gallery", event_id=event_id))


@app.route("/student/events/<int:event_id>/gallery")
@role_required("student")
def student_event_gallery(event_id):
    """Student gallery view for an approved event."""
    event = Event.query.get_or_404(event_id)
    if event.status != "approved":
        flash("This event is not approved yet.", "danger")
        return redirect(url_for("events"))
    reg = Registration.query.filter_by(user_id=current_user.id, event_id=event.id).first()
    can_upload = reg is not None
    gallery = EventGallery.query.filter_by(event_id=event_id).order_by(EventGallery.uploaded_at.desc()).all()
    return render_template("student/event_gallery.html", event=event, gallery=gallery, can_upload=can_upload)

@app.route("/certificate/<int:registration_id>")
@login_required
def certificate(registration_id):
    from reportlab.lib.colors import HexColor
    reg = Registration.query.get_or_404(registration_id)
    if reg.user_id != current_user.id and current_user.role not in ("admin","organizer"):
        abort(403)
    if not reg.attended:
        flash("Certificate is available after attendance is recorded.", "warning")
        return redirect(url_for("my_registrations"))

    existing = DigitalCertificate.query.filter_by(registration_id=reg.id).first()
    if not existing:
        existing = DigitalCertificate(
            registration_id=reg.id,
            certificate_code=reg.ticket_code,
            achievement=f"Participation in {reg.event.title}",
            issued_date=datetime.utcnow(),
            verified=True,
            verification_code=secrets.token_urlsafe(16)
        )
        db.session.add(existing)
        db.session.commit()

    primary = HexColor("#6366f1")
    dark = HexColor("#1e293b")
    gold = HexColor("#d97706")
    white = HexColor("#ffffff")
    border_color = HexColor("#cbd5e1")

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, pageCompression=0)
    w, h = A4
    c.setTitle(f"Certificate - {reg.ticket_code}")

    c.setFillColor(white)
    c.rect(0, 0, w, h, fill=1, stroke=0)

    c.setStrokeColor(primary)
    c.setLineWidth(6)
    c.rect(20, 20, w-40, h-40, fill=0)
    c.setLineWidth(2)
    c.setStrokeColor(border_color)
    c.rect(40, 40, w-80, h-80, fill=0)

    c.setFillColor(gold)
    c.setStrokeColor(gold)
    c.setLineWidth(1.5)
    c.circle(w/2, h-140, 50, fill=1, stroke=1)
    c.setFillColor(dark)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(w/2, h-150, COLLEGE.upper())

    c.setFillColor(dark)
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(w/2, h-240, "CERTIFICATE OF PARTICIPATION")

    c.setFont("Helvetica-Oblique", 14)
    c.drawCentredString(w/2, h-290, "This is to certify that")

    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(primary)
    c.drawCentredString(w/2, h-340, reg.user.name)

    c.setFillColor(dark)
    c.setFont("Helvetica", 15)
    c.drawCentredString(w/2, h-385, f"successfully participated in")
    c.setFont("Helvetica-Bold", 17)
    c.drawCentredString(w/2, h-365, reg.event.title)
    c.setFont("Helvetica", 13)
    c.drawCentredString(w/2, h-410, f"held at {reg.event.venue} on {reg.event.date.strftime('%d %B %Y')}")
    c.setFont("Helvetica", 12)
    c.drawCentredString(w/2, h-435, f"Certificate Code: {existing.certificate_code} | Verification Code: {existing.verification_code}")

    c.line(w/2 - 120, 550, w/2 - 40, 550)
    c.line(w/2 + 40, 550, w/2 + 120, 550)
    c.setFont("Helvetica", 10)
    c.drawCentredString(w/2 - 80, 535, "Event Organizer")
    c.drawCentredString(w/2 + 80, 535, "HOD, " + (reg.user.department or "Student Affairs"))

    c.setFillColor(HexColor("#94a3b8"))
    c.setFont("Helvetica", 9)
    c.drawCentredString(w/2, 30, f"{COLLEGE} — {SHORT} Campus Event Management System | {SHORT.lower()}@agc.edu.in")
    c.save()
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=f"certificate-{reg.ticket_code}.pdf")

@app.route("/admin/dashboard")
@role_required("admin")
def admin_dashboard():
    stats = {
        "users": User.query.count(),
        "students": User.query.filter_by(role="student").count(),
        "organizers": User.query.filter_by(role="organizer").count(),
        "events": Event.query.count(),
        "pending_events": Event.query.filter(Event.status.in_(["pending", "waiting"])).count(),
        "approved_events": Event.query.filter_by(status="approved").count(),
        "rejected_events": Event.query.filter_by(status="rejected").count(),
        "upcoming_events": Event.query.filter(Event.status=="approved", Event.date >= datetime.utcnow().date()).count(),
        "completed_events": PastEvent.query.count(),
        "registrations": Registration.query.count(),
        "attendees": Registration.query.filter_by(attended=True).count(),
        "notices": Notice.query.filter_by(status="published").count(),
    }
    events = Event.query.order_by(Event.created_at.desc()).limit(8).all()
    return render_template("admin/dashboard.html", stats=stats, events=events)

@app.route("/admin/users")
@role_required("admin")
def admin_users():
    page = request.args.get("page", 1, type=int)
    pagination = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template("admin/users.html", users=pagination.items, pagination=pagination)

@app.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@role_required("admin")
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot block your own admin account.", "warning")
    else:
        user.is_active_account = not user.is_active_account
        db.session.commit()
        flash("User status updated.", "success")
    return redirect(url_for("admin_users"))

@app.route("/admin/events")
@role_required("admin")
def admin_events():
    page = request.args.get("page", 1, type=int)
    pagination = Event.query.order_by(Event.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template("admin/events.html", events=pagination.items, pagination=pagination)

@app.route("/admin/events/<int:event_id>/<action>", methods=["POST"])
@role_required("admin")
def event_action(event_id, action):
    event = Event.query.get_or_404(event_id)
    if action not in ("approve", "reject", "request_changes", "approve_change", "reject_change"):
        abort(400)
    feedback = clean_text(request.form.get("feedback") or request.form.get("rejection_reason"), 2000)
    previous_status = event.status
    if action == "approve":
        event.status = "approved"
        event.change_status = "none"
        event.rejection_reason = None
        message = f"{event.title} has been approved by admin."
    elif action == "reject":
        event.status = "rejected"
        event.change_status = "none"
        event.rejection_reason = feedback or "Admin rejected this event."
        message = f"{event.title} has been rejected by admin."
    elif action == "request_changes":
        event.status = "changes_requested"
        event.change_status = "pending"
        event.rejection_reason = feedback or "Admin requested changes."
        message = f"Changes were requested for {event.title}."
    elif action == "approve_change":
        event.status = "approved"
        event.change_status = "none"
        event.original_data = None
        event.rejection_reason = None
        message = f"Changes to {event.title} have been approved."
    else:
        if event.original_data:
            event.date = datetime.strptime(event.original_data["date"], "%Y-%m-%d").date()
            event.start_time = event.original_data["start_time"]
            event.end_time = event.original_data["end_time"]
            event.venue = event.original_data["venue"]
            event.capacity = event.original_data["capacity"]
            event.registration_deadline = datetime.strptime(event.original_data["registration_deadline"], "%Y-%m-%d").date() if event.original_data.get("registration_deadline") else None
        event.status = "approved"
        event.change_status = "none"
        event.original_data = None
        event.rejection_reason = feedback or event.rejection_reason
        message = f"Changes to {event.title} were rejected. Previous information restored."
    db.session.add(EventApprovalHistory(
        event_id=event.id,
        actor_id=current_user.id,
        action=action,
        from_status=previous_status,
        to_status=event.status,
        comments=feedback,
    ))
    create_notification(event.organizer_id, "Event approval update", message)
    audit(current_user, f"event.{action}", "Event", event.id, message)
    db.session.commit()
    flash(message, "success" if action in {"approve", "approve_change"} else "warning")
    return redirect(url_for("admin_events"))

@app.route("/admin/registrations")
@role_required("admin")
def admin_registrations():
    page = request.args.get("page", 1, type=int)
    pagination = Registration.query.order_by(Registration.registered_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template("admin/registrations.html", registrations=pagination.items, pagination=pagination)

@app.route("/admin/registrations/export")
@role_required("admin")
def export_registrations():
    """Export all registrations as a CSV file."""
    import csv, io
    regs = Registration.query.order_by(Registration.registered_at.desc()).all()
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(["Ticket Code", "Participant Name", "Email", "Roll No", "Department",
                     "Event Title", "Event Date", "Venue", "Registration Date",
                     "Status", "Payment Status", "Attended", "Check-in Time"])
    for r in regs:
        writer.writerow([
            r.ticket_code,
            r.user.name,
            r.user.email,
            r.user.roll_no or "",
            r.user.department or "",
            r.event.title,
            r.event.date.strftime('%Y-%m-%d') if r.event.date else "",
            r.event.venue,
            r.registered_at.strftime('%Y-%m-%d %H:%M:%S'),
            r.status,
            r.payment_status,
            "Yes" if r.attended else "No",
            r.checkin_time.strftime('%Y-%m-%d %H:%M:%S') if r.checkin_time else "",
        ])
    buf = BytesIO()
    buf.write(output.getvalue().encode('utf-8'))
    buf.seek(0)
    return send_file(buf, mimetype="text/csv", as_attachment=True, download_name=f"cems_registrations_{datetime.utcnow().strftime('%Y%m%d')}.csv")

@app.route("/organizer/events/<int:event_id>/registrations/export")
@role_required("organizer")
def export_event_registrations(event_id):
    """Export a specific event's registrations as a CSV file."""
    import csv, io
    event = Event.query.get_or_404(event_id)
    if event.organizer_id != current_user.id:
        abort(403)
    regs = Registration.query.filter_by(event_id=event.id).order_by(Registration.registered_at.desc()).all()
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(["Ticket Code", "Participant Name", "Email", "Roll No", "Department",
                     "Registration Date", "Status", "Payment Status", "Attended", "Check-in Time"])
    for r in regs:
        writer.writerow([
            r.ticket_code,
            r.user.name,
            r.user.email,
            r.user.roll_no or "",
            r.user.department or "",
            r.registered_at.strftime('%Y-%m-%d %H:%M:%S'),
            r.status,
            r.payment_status,
            "Yes" if r.attended else "No",
            r.checkin_time.strftime('%Y-%m-%d %H:%M:%S') if r.checkin_time else "",
        ])
    buf = BytesIO()
    buf.write(output.getvalue().encode('utf-8'))
    buf.seek(0)
    return send_file(buf, mimetype="text/csv", as_attachment=True, download_name=f"{event.title.replace(' ','_')}_registrations_{datetime.utcnow().strftime('%Y%m%d')}.csv")

@app.route("/admin/reports")
@role_required("admin")
def admin_reports():
    total_revenue = sum(r.event.fee for r in Registration.query.filter(Registration.payment_status.in_(["paid", "successful"])).all())
    feedbacks = Feedback.query.all()
    avg = round(sum(f.rating for f in feedbacks)/len(feedbacks), 2) if feedbacks else 0
    return render_template("admin/reports.html",
                           total_revenue=total_revenue,
                           avg_rating=avg,
                           users=User.query.count(),
                           events=Event.query.count(),
                           registrations=Registration.query.count(),
                           attendees=Registration.query.filter_by(attended=True).count())

@app.route("/admin/notifications", methods=["GET","POST"])
@role_required("admin")
def admin_notifications():
    users = User.query.filter(User.role != "admin").all()
    if request.method == "POST":
        title = request.form.get("title","Campus Update")
        message = request.form.get("message","")
        selected = request.form.get("audience","all")
        targets = users if selected == "all" else [u for u in users if u.role == selected]
        for u in targets:
            create_notification(u.id, title, message)
        db.session.commit()
        flash(f"Notification sent to {len(targets)} users.", "success")
    return render_template("admin/notifications.html")


@app.route("/admin/venues", methods=["GET","POST"])
@role_required("admin")
def admin_venues():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        location = request.form.get("location","").strip()
        capacity = int(request.form.get("capacity",100))
        if name:
            db.session.add(Venue(name=name, location=location, capacity=capacity))
            db.session.commit()
            flash("Venue added.", "success")
    venues = Venue.query.order_by(Venue.name).all()
    return render_template("admin/venues.html", venues=venues)


@app.route("/organizer/support/<module>", methods=["GET","POST"])
@role_required("organizer")
def organizer_support(module):
    if module not in ("volunteers","judges","sponsors"):
        abort(404)
    events = Event.query.filter_by(organizer_id=current_user.id).all()
    if request.method == "POST":
        event_id = int(request.form.get("event_id"))
        if not any(e.id == event_id for e in events):
            abort(403)
        if module == "volunteers":
            db.session.add(Volunteer(name=request.form.get("name"), email=request.form.get("email"),
                                     event_id=event_id, task=request.form.get("task")))
        elif module == "judges":
            db.session.add(Judge(name=request.form.get("name"), email=request.form.get("email"),
                                 event_id=event_id, criteria=request.form.get("criteria")))
        else:
            db.session.add(Sponsor(name=request.form.get("name"), contact=request.form.get("contact"),
                                   event_id=event_id, contribution=float(request.form.get("contribution",0) or 0)))
        db.session.commit()
        module_name = module.rstrip('s').title()
        flash(f"{module_name} added.", "success")
    model = {"volunteers": Volunteer, "judges": Judge, "sponsors": Sponsor}[module]
    rows = model.query.filter(model.event_id.in_([e.id for e in events])).order_by(model.id.desc()).all() if events else []
    return render_template("organizer/support.html", module=module, events=events, rows=rows)

@app.route("/health")
def health():
    return {"status":"ok","college":COLLEGE,"time":datetime.utcnow().isoformat()}

# ==============================
# PAST EVENTS
# ==============================

def archive_completed_events():
    now = datetime.utcnow()
    completed = Event.query.filter(
        Event.status == "approved",
        Event.date < now.date()
    ).all()
    for event in completed:
        if not PastEvent.query.filter_by(event_id=event.id).first():
            db.session.add(PastEvent(event_id=event.id))
    db.session.commit()

@app.route("/past-events")
def past_events():
    archive_completed_events()
    q = request.args.get("q","").strip()
    category = request.args.get("category","").strip()
    venue = request.args.get("venue","").strip()
    page = request.args.get("page", 1, type=int)
    query = Event.query.join(PastEvent, Event.id == PastEvent.event_id).filter(Event.status == "approved")
    if q:
        query = query.filter(Event.title.ilike(f"%{q}%"))
    if category:
        query = query.filter(Event.category == category)
    if venue:
        query = query.filter(Event.venue.ilike(f"%{venue}%"))
    pagination = query.order_by(Event.date.desc()).paginate(page=page, per_page=12, error_out=False)
    categories = [r[0] for r in db.session.query(Event.category).distinct().all()]
    venues = [r[0] for r in db.session.query(Event.venue).distinct().all()]
    return render_template("past_events.html", events=pagination.items, categories=categories, venues=venues, q=q, category=category, venue=venue, pagination=pagination)

@app.route("/past-events/<int:event_id>")
def past_event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    if not PastEvent.query.filter_by(event_id=event_id).first():
        abort(404)
    return render_template("past_event_detail.html", event=event)

# ==============================
# NOTICE BOARD
# ==============================

@app.route("/notices")
def notices():
    page = request.args.get("page", 1, type=int)
    pagination = Notice.query.filter_by(status="published").order_by(Notice.published_at.desc()).paginate(page=page, per_page=9, error_out=False)
    return render_template("notices.html", notices=pagination.items, pagination=pagination)

@app.route("/notices/<int:notice_id>")
def board_notice_detail(notice_id):
    notice = Notice.query.get_or_404(notice_id)
    if notice.status != "published" and (not current_user.is_authenticated or current_user.role not in ("admin", "organizer")):
        abort(404)
    return render_template("notice_detail.html", notice=notice)

@app.route("/admin/notices", methods=["GET","POST"])
@role_required("admin")
def admin_notices():
    if request.method == "POST":
        title = request.form.get("title","").strip()
        description = request.form.get("description","").strip()
        category = request.form.get("category","General")
        event_id = request.form.get("event_id")
        image = request.files.get("image")
        image_path = None
        if image and image.filename:
            from werkzeug.utils import secure_filename
            filename = secure_filename(image.filename)
            image_path = f"uploads/notices/{filename}"
            import os
            os.makedirs("static/uploads/notices", exist_ok=True)
            image.save(os.path.join("static", image_path))
        notice = Notice(
            title=title,
            description=description,
            category=category,
            event_id=int(event_id) if event_id else None,
            image=image_path,
            published_by=current_user.id,
            status="published"
        )
        db.session.add(notice)
        db.session.commit()
        flash("Notice published.", "success")
        return redirect(url_for("admin_notices"))
    events = Event.query.filter_by(status="approved").all()
    page = request.args.get("page", 1, type=int)
    pagination = Notice.query.order_by(Notice.published_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template("admin/notices.html", events=events, notices=pagination.items, pagination=pagination)

@app.route("/admin/notices/<int:notice_id>/delete", methods=["POST"])
@role_required("admin")
def delete_notice(notice_id):
    notice = Notice.query.get_or_404(notice_id)
    db.session.delete(notice)
    db.session.commit()
    flash("Notice deleted.", "success")
    return redirect(url_for("admin_notices"))

# ==============================
# EVENT GALLERY
# ==============================

@app.route("/events/<int:event_id>/gallery", methods=["GET","POST"])
def event_gallery(event_id):
    event = Event.query.get_or_404(event_id)
    is_organizer = current_user.is_authenticated and event.organizer_id == current_user.id
    is_admin = current_user.is_authenticated and current_user.role == "admin"
    can_upload = is_organizer or is_admin
    if request.method == "POST" and can_upload:
        images = request.files.getlist("images")
        import os
        os.makedirs("static/uploads/gallery", exist_ok=True)
        for image in images:
            if image and image.filename:
                from werkzeug.utils import secure_filename
                filename = secure_filename(image.filename)
                path = f"uploads/gallery/{event_id}_{filename}"
                image.save(os.path.join("static", path))
                db.session.add(EventGallery(
                    event_id=event_id,
                    image=path,
                    uploaded_by=current_user.id
                ))
        db.session.commit()
        flash("Images uploaded.", "success")
        return redirect(url_for("event_gallery", event_id=event_id))
    gallery = EventGallery.query.filter_by(event_id=event_id).order_by(EventGallery.uploaded_at.desc()).all()
    return render_template("event_gallery.html", event=event, gallery=gallery, can_upload=can_upload)

# ==============================
# PAST EVENT PDF
# ==============================

@app.route("/past-events/<int:event_id>/pdf")
@login_required
def past_event_pdf(event_id):
    event = Event.query.get_or_404(event_id)
    if not PastEvent.query.filter_by(event_id=event_id).first():
        abort(404)
    if current_user.role not in ("admin", "organizer") or (current_user.role == "organizer" and event.organizer_id != current_user.id):
        abort(403)
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setTitle(f"{event.title} - Event Report")
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(w/2, h-120, event.title.upper())
    c.setFont("Helvetica", 12)
    c.drawCentredString(w/2, h-150, f"{event.category} | {event.date.strftime('%d %B %Y')}")
    c.line(80, h-170, w-80, h-170)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(80, h-210, "Event Details")
    c.setFont("Helvetica", 11)
    details = [
        f"Organizer: {event.organizer.name}",
        f"Date: {event.date.strftime('%d %B %Y')}",
        f"Time: {event.start_time} - {event.end_time}",
        f"Venue: {event.venue}",
        f"Capacity: {event.capacity}",
        f"Registrations: {len(event.registrations)}",
        f"Attendees: {sum(1 for r in event.registrations if r.attended)}",
        f"Status: {event.status}",
    ]
    y = h-240
    for line in details:
        c.drawString(80, y, line)
        y -= 20
    c.setFont("Helvetica-Bold", 14)
    c.drawString(80, y-20, "Description")
    c.setFont("Helvetica", 11)
    y -= 50
    desc_lines = event.description.splitlines()[:10]
    for line in desc_lines:
        c.drawString(80, y, line[:90])
        y -= 16
    c.save()
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=f"event-report-{event.id}.pdf")

@app.errorhandler(404)
def not_found(error):
    return render_template("errors/404.html"), 404

@app.errorhandler(403)
def forbidden(error):
    return render_template("errors/403.html"), 403

with app.app_context():
    seed_data()

if __name__ == "__main__":
    app.run(debug=True)
