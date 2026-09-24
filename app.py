
from datetime import datetime, timedelta
from io import BytesIO
from functools import wraps
import os
import qrcode
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request, flash, send_file, abort
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
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

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

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

    email = db.Column(
        db.String(160),
        unique=True,
        nullable=False
    )

    mobile = db.Column(db.String(20))

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(30),
        default="student"
    )

    department = db.Column(
        db.String(100)
    )

    roll_no = db.Column(
        db.String(50)
    )

    is_active_account = db.Column(
        db.Boolean,
        default=True
    )

    reset_token = db.Column(
        db.String(100)
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password
        )
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
    registration_deadline = db.Column(db.Date)
    fee = db.Column(db.Float, default=0)
    status = db.Column(db.String(30), default="pending")
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
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", backref="registrations")
    event = db.relationship("Event", backref="registrations")

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    message = db.Column(db.Text, nullable=False)
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
    name = db.Column(db.String(150), nullable=False)
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

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.context_processor
def inject_globals():
    unread = 0
    if current_user.is_authenticated:
        unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return {"college_name": COLLEGE, "college_short": SHORT, "unread_notifications": unread, "agc_profile": AGC_PROFILE, "agc_updates": AGC_UPDATES}

def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user.role not in roles:
                flash("You do not have permission to access this page.", "danger")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator

       
def create_notification(user_id, title, message):
    db.session.add(Notification(user_id=user_id, title=title, message=message))
    db.session.commit()

def seed_data():
    db.create_all()
    if User.query.count() == 0:
        admin = User(name="AGC Admin", email="admin@agc.local", role="admin", department="Administration")
        admin.set_password("Admin@123")
        organizer = User(name="AGC Event Organizer", email="organizer@agc.local", role="organizer", department="Student Affairs")
        organizer.set_password("Organizer@123")
        student = User(name="Rahul Sharma", email="student@agc.local", role="student", department="Computer Science", roll_no="21CS1001", mobile="9876543210")
        student.set_password("Student@123")
        db.session.add_all([admin, organizer, student])
        db.session.flush()

        venues = [
            Venue(name="Main Auditorium", location="AGC Campus", capacity=500),
            Venue(name="Open Ground", location="AGC Campus", capacity=1000),
            Venue(name="Seminar Hall", location="Computer Science Block", capacity=250),
            Venue(name="Innovation Lab", location="Engineering Block", capacity=120),
        ]
        db.session.add_all(venues)
        db.session.flush()

        sample = [
            # Academic Events
            ("AI & Machine Learning Seminar", "Academic", "free", 2026, 9, 5, "10:00 AM", "12:00 PM", "Seminar Hall", 150, 0),
            ("Research Paper Writing Workshop", "Academic", "free", 2026, 9, 12, "2:00 PM", "4:00 PM", "Seminar Hall", 100, 0),
            ("NPTEL & Digital Learning Orientation", "Academic", "free", 2026, 9, 18, "11:00 AM", "1:00 PM", "Seminar Hall", 250, 0),
            ("Industrial Research Trends 2026", "Academic", "free", 2026, 9, 25, "10:00 AM", "2:00 PM", "Main Auditorium", 300, 0),
            ("Entrepreneurship & Innovation Lecture", "Academic", "paid", 2026, 10, 2, "3:00 PM", "5:00 PM", "Innovation Lab", 120, 99),
            
            # Technical Events
            ("AGC Tech Fest 2026", "Technical", "free", 2026, 9, 12, "10:00 AM", "5:00 PM", "Main Auditorium", 500, 0),
            ("Coding Hackathon - 24 Hours", "Technical", "free", 2026, 9, 28, "10:00 AM", "10:00 AM", "Innovation Lab", 200, 0),
            ("Web Development Bootcamp", "Technical", "paid", 2026, 10, 5, "9:00 AM", "5:00 PM", "Computer Lab", 80, 299),
            ("Mobile App Development Challenge", "Technical", "free", 2026, 10, 15, "2:00 PM", "6:00 PM", "Innovation Lab", 100, 0),
            ("Cybersecurity Workshop & Hands-on", "Technical", "paid", 2026, 10, 22, "10:00 AM", "4:00 PM", "Computer Lab", 60, 199),
            ("Cloud Computing Fundamentals", "Technical", "free", 2026, 11, 3, "11:00 AM", "1:00 PM", "Seminar Hall", 150, 0),
            ("Data Science & Analytics Masterclass", "Technical", "paid", 2026, 11, 10, "10:00 AM", "5:00 PM", "Computer Lab", 100, 249),
            
            # Cultural Events
            ("AGC Cultural Fiesta 2026", "Cultural", "free", 2026, 9, 19, "11:00 AM", "5:00 PM", "Open Ground", 1000, 0),
            ("Classical Music Concert", "Cultural", "free", 2026, 10, 8, "6:00 PM", "9:00 PM", "Main Auditorium", 500, 0),
            ("Contemporary Dance Performance", "Cultural", "free", 2026, 10, 16, "7:00 PM", "9:30 PM", "Open Ground", 800, 0),
            ("Art Exhibition & Painting Workshop", "Cultural", "free", 2026, 10, 24, "10:00 AM", "4:00 PM", "Innovation Lab", 200, 0),
            ("Theater & Dramatics Play", "Cultural", "free", 2026, 11, 5, "7:00 PM", "9:30 PM", "Main Auditorium", 600, 0),
            ("Poetry & Creative Writing Festival", "Cultural", "free", 2026, 11, 12, "5:00 PM", "8:00 PM", "Seminar Hall", 300, 0),
            
            # Sports Events
            ("AGC Sports & Athletic Meet", "Sports", "free", 2026, 11, 7, "9:00 AM", "5:00 PM", "Open Ground", 1000, 0),
            ("Cricket Tournament Finals", "Sports", "free", 2026, 9, 20, "3:00 PM", "6:00 PM", "Open Ground", 500, 0),
            ("Football League Championship", "Sports", "free", 2026, 10, 12, "4:00 PM", "7:00 PM", "Open Ground", 800, 0),
            ("Badminton Singles & Doubles", "Sports", "free", 2026, 10, 28, "9:00 AM", "5:00 PM", "Sports Complex", 150, 0),
            ("Basketball 3-on-3 Tournament", "Sports", "free", 2026, 11, 14, "10:00 AM", "4:00 PM", "Sports Complex", 200, 0),
            ("Volleyball Championship", "Sports", "free", 2026, 11, 21, "3:00 PM", "7:00 PM", "Sports Complex", 250, 0),
            
            # Workshop Events
            ("AI & Emerging Technologies Workshop", "Workshop", "free", 2026, 10, 2, "10:00 AM", "2:00 PM", "Seminar Hall", 250, 0),
            ("Digital Marketing & Social Media", "Workshop", "paid", 2026, 10, 9, "2:00 PM", "5:00 PM", "Innovation Lab", 100, 149),
            ("Leadership & Team Management", "Workshop", "free", 2026, 10, 16, "10:00 AM", "1:00 PM", "Main Auditorium", 300, 0),
            ("Public Speaking & Presentation Skills", "Workshop", "free", 2026, 10, 23, "3:00 PM", "5:00 PM", "Seminar Hall", 200, 0),
            ("Graphic Design & UI/UX Basics", "Workshop", "paid", 2026, 11, 1, "10:00 AM", "4:00 PM", "Computer Lab", 80, 199),
            ("Environmental Awareness & Sustainability", "Workshop", "free", 2026, 11, 8, "2:00 PM", "4:00 PM", "Main Auditorium", 400, 0),
            
            # Entrepreneurship Events
            ("AGC Innovation & Entrepreneurship Summit", "Entrepreneurship", "paid", 2026, 10, 10, "10:00 AM", "4:00 PM", "Innovation Lab", 120, 199),
            ("Startup Pitch Competition", "Entrepreneurship", "free", 2026, 10, 25, "3:00 PM", "6:00 PM", "Main Auditorium", 500, 0),
            ("Business Model Canvas Workshop", "Entrepreneurship", "free", 2026, 11, 2, "10:00 AM", "12:30 PM", "Innovation Lab", 150, 0),
            ("Funding & Investor Pitching Session", "Entrepreneurship", "paid", 2026, 11, 9, "2:00 PM", "5:00 PM", "Innovation Lab", 100, 249),
            ("Social Enterprise & Impact Startup", "Entrepreneurship", "free", 2026, 11, 15, "11:00 AM", "1:00 PM", "Seminar Hall", 200, 0),
        ]
        for title, cat, typ, y, m, d, st, et, venue, cap, fee in sample:
            e = Event(title=title, category=cat, event_type=typ, date=datetime(y,m,d).date(),
                      start_time=st, end_time=et, venue=venue,
                      description=f"{title} is a campus event at {COLLEGE}, designed for students, faculty, clubs and invited guests to learn, participate, collaborate and showcase talent. This event features industry experts, peer learning, and hands-on experience.",
                      highlights="Student participation\nIndustry interaction\nCompetitions & activities\nNetworking & learning\nCertificates\nRefreshments",
                      capacity=cap, registration_deadline=datetime(y,m,d).date()-timedelta(days=2),
                      fee=fee, status="approved", organizer_id=organizer.id)
            db.session.add(e)
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

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        mobile = request.form.get("mobile", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        role = request.form.get("role", "student")
        department = request.form.get("department", "").strip()
        roll_no = request.form.get("roll_no", "").strip()

        # Required fields
        if not all([name, email, password]):
            flash(
                "Name, email and password are required.",
                "danger"
            )
            return render_template("auth/register.html")

        # Confirm password
        if password != confirm:
            flash(
                "Passwords do not match.",
                "danger"
            )
            return render_template("auth/register.html")

        # Minimum password length
        if len(password) < 8:
            flash(
                "Password must be at least 8 characters.",
                "danger"
            )
            return render_template("auth/register.html")

        # Check existing account
        if User.query.filter_by(email=email).first():
            flash(
                "An account with this email already exists.",
                "danger"
            )
            return render_template("auth/register.html")

        # Allowed roles
        if role not in ("student", "organizer"):
            role = "student"

        # Create new user
        user = User(
            name=name,
            email=email,
            mobile=mobile,
            role=role,
            department=department,
            roll_no=roll_no
        )

        # Hash password
        user.set_password(password)

        # Save user
        db.session.add(user)
        db.session.commit()

        # Automatically login the new user
        login_user(
            user,
            remember=True
        )

        flash(
            "Account created successfully!",
            "success"
        )

        # Directly open dashboard
        return redirect(url_for("dashboard"))

    return render_template("auth/register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")

        elif not user.is_active_account:
            flash("Your account has been blocked by admin.", "danger")

        else:
            login_user(
                user,
                remember=bool(request.form.get("remember"))
            )

            return redirect(url_for("dashboard"))

    return render_template("auth/login.html")

@app.route("/forgot-password", methods=["GET", "POST"])
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
    return redirect(url_for("student_dashboard"))

@app.route("/events")
def events():
    q = request.args.get("q","").strip()
    category = request.args.get("category","").strip()
    status = request.args.get("status","").strip()
    query = Event.query.filter_by(status="approved")
    if q:
        query = query.filter(Event.title.ilike(f"%{q}%"))
    if category:
        query = query.filter_by(category=category)
    today = datetime.utcnow().date()
    if status == "upcoming":
        query = query.filter(Event.date >= today)
    elif status == "completed":
        query = query.filter(Event.date < today)
    event_list = query.order_by(Event.date.asc()).all()
    categories = [r[0] for r in db.session.query(Event.category).distinct().all()]
    return render_template("events.html", events=event_list, categories=categories, q=q, category=category, status=status)

@app.route("/events/<int:event_id>")
def event_details(event_id):
    event = Event.query.get_or_404(event_id)
    if event.status != "approved" and (not current_user.is_authenticated or current_user.role not in ("admin","organizer")):
        abort(404)
    registered = False
    if current_user.is_authenticated:
        registered = Registration.query.filter_by(user_id=current_user.id, event_id=event.id).first() is not None
    seats = event.capacity - Registration.query.filter_by(event_id=event.id, status="confirmed").count()
    return render_template("event_details.html", event=event, registered=registered, seats=max(seats,0))

@app.route("/student/dashboard")
@role_required("student")
def student_dashboard():
    upcoming = Event.query.filter(Event.status=="approved", Event.date >= datetime.utcnow().date()).order_by(Event.date).limit(4).all()
    regs = Registration.query.filter_by(user_id=current_user.id).count()
    attended = Registration.query.filter_by(user_id=current_user.id, attended=True).count()
    tickets = Registration.query.filter_by(user_id=current_user.id, status="confirmed").count()
    return render_template("student/dashboard.html", upcoming=upcoming, regs=regs, attended=attended, tickets=tickets)

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
    count = Registration.query.filter_by(event_id=event.id, status="confirmed").count()
    if count >= event.capacity:
        flash("This event is full.", "danger")
        return redirect(url_for("event_details", event_id=event.id))
    if event.registration_deadline and datetime.utcnow().date() > event.registration_deadline:
        flash("Registration deadline has passed.", "danger")
        return redirect(url_for("event_details", event_id=event.id))
    if request.method == "POST":
        if event.fee > 0:
            return redirect(url_for("demo_payment", event_id=event.id))
        ticket = "AGC-" + secrets.token_hex(4).upper()
        reg = Registration(ticket_code=ticket, user_id=current_user.id, event_id=event.id,
                           status="confirmed", payment_status="free")
        db.session.add(reg)
        create_notification(current_user.id, "Registration confirmed",
                            f"You are registered for {event.title}. Ticket: {ticket}")
        db.session.commit()
        flash("Registration successful. Your digital ticket is ready.", "success")
        return redirect(url_for("ticket", registration_id=reg.id))
    return render_template("student/register_event.html", event=event)

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
    img = qrcode.make(reg.ticket_code)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png", download_name=f"{reg.ticket_code}.png")

@app.route("/student/notifications")
@role_required("student")
def student_notifications():
    notes = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    for n in notes:
        n.is_read = True
    db.session.commit()
    return render_template("student/notifications.html", notifications=notes)

@app.route("/student/profile", methods=["GET","POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.name = request.form.get("name","").strip()
        current_user.mobile = request.form.get("mobile","").strip()
        current_user.department = request.form.get("department","").strip()
        current_user.roll_no = request.form.get("roll_no","").strip()
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("profile"))
    return render_template("student/profile.html")

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
    revenue = sum(e.fee * len([r for r in e.registrations if r.payment_status=="paid"]) for e in evs)
    return render_template("organizer/dashboard.html", events=evs, total_reg=total_reg, total_att=total_att, revenue=revenue)

@app.route("/organizer/events/create", methods=["GET","POST"])
@role_required("organizer")
def create_event():
    if request.method == "POST":
        try:
            event = Event(
                title=request.form.get("title","").strip(),
                category=request.form.get("category","Other"),
                event_type=request.form.get("event_type","free"),
                date=datetime.strptime(request.form.get("date"), "%Y-%m-%d").date(),
                start_time=request.form.get("start_time"),
                end_time=request.form.get("end_time"),
                venue=request.form.get("venue"),
                description=request.form.get("description",""),
                highlights=request.form.get("highlights",""),
                capacity=int(request.form.get("capacity",100)),
                registration_deadline=datetime.strptime(request.form.get("registration_deadline"), "%Y-%m-%d").date() if request.form.get("registration_deadline") else None,
                fee=float(request.form.get("fee",0) or 0),
                status="pending",
                organizer_id=current_user.id
            )
            db.session.add(event)
            db.session.commit()
            create_notification(current_user.id, "Event submitted", f"{event.title} was submitted for admin review.")
            db.session.commit()
            flash("Event created and sent for admin approval.", "success")
            return redirect(url_for("organizer_dashboard"))
        except Exception as exc:
            db.session.rollback()
            flash(f"Could not create event: {exc}", "danger")
    return render_template("organizer/create_event.html")

@app.route("/organizer/events/<int:event_id>/manage", methods=["GET","POST"])
@role_required("organizer")
def manage_event(event_id):
    event = Event.query.get_or_404(event_id)
    if event.organizer_id != current_user.id:
        abort(403)
    if request.method == "POST":
        event.title = request.form.get("title")
        event.category = request.form.get("category")
        event.venue = request.form.get("venue")
        event.description = request.form.get("description")
        event.highlights = request.form.get("highlights")
        event.capacity = int(request.form.get("capacity", event.capacity))
        db.session.commit()
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
        code = request.form.get("ticket_code","").strip().upper()
        reg = Registration.query.filter_by(ticket_code=code).first()
        if not reg:
            flash("Ticket not found.", "danger")
        elif reg.event.organizer_id != current_user.id:
            flash("This ticket belongs to another organizer.", "danger")
        elif reg.attended:
            flash("Already checked in.", "warning")
            result = reg
        else:
            reg.attended = True
            reg.checkin_time = datetime.utcnow()
            create_notification(reg.user_id, "Check-in successful", f"You checked in for {reg.event.title}.")
            db.session.commit()
            flash(f"{reg.user.name} checked in successfully.", "success")
            result = reg
    return render_template("organizer/checkin.html", result=result)

@app.route("/organizer/reports")
@role_required("organizer")
def organizer_reports():
    events = Event.query.filter_by(organizer_id=current_user.id).all()
    total_events = len(events)
    total_reg = sum(len(e.registrations) for e in events)
    total_att = sum(1 for e in events for r in e.registrations if r.attended)
    revenue = sum(e.fee * sum(1 for r in e.registrations if r.payment_status=="paid") for e in events)
    return render_template("organizer/reports.html", events=events, total_events=total_events,
                           total_reg=total_reg, total_att=total_att, revenue=revenue)


@app.route("/payment/<int:event_id>", methods=["GET","POST"])
@role_required("student")
def demo_payment(event_id):
    event = Event.query.get_or_404(event_id)
    existing = Registration.query.filter_by(user_id=current_user.id, event_id=event.id).first()
    if existing:
        return redirect(url_for("ticket", registration_id=existing.id))
    if event.fee <= 0:
        return redirect(url_for("register_event", event_id=event.id))
    if request.method == "POST":
        ticket = "AGC-" + secrets.token_hex(4).upper()
        reg = Registration(ticket_code=ticket, user_id=current_user.id, event_id=event.id,
                           status="confirmed", payment_status="paid")
        db.session.add(reg)
        create_notification(current_user.id, "Payment successful",
                            f"Demo payment recorded for {event.title}. Ticket: {ticket}")
        db.session.commit()
        flash("Demo payment successful. Your ticket has been generated.", "success")
        return redirect(url_for("ticket", registration_id=reg.id))
    return render_template("student/payment.html", event=event)

@app.route("/certificate/<int:registration_id>")
@login_required
def certificate(registration_id):
    reg = Registration.query.get_or_404(registration_id)
    if reg.user_id != current_user.id and current_user.role not in ("admin","organizer"):
        abort(403)
    if not reg.attended:
        flash("Certificate is available after attendance is recorded.", "warning")
        return redirect(url_for("my_registrations"))
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setTitle("CEMS Certificate")
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(w/2, h-150, COLLEGE.upper())
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(w/2, h-230, "CERTIFICATE OF PARTICIPATION")
    c.setFont("Helvetica", 16)
    c.drawCentredString(w/2, h-300, "This certificate is proudly presented to")
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(w/2, h-350, reg.user.name)
    c.setFont("Helvetica", 15)
    c.drawCentredString(w/2, h-410, f"for participating in {reg.event.title}")
    c.drawCentredString(w/2, h-440, f"held at {reg.event.venue} on {reg.event.date.strftime('%d %B %Y')}")
    c.line(100, 120, w-100, 120)
    c.setFont("Helvetica", 11)
    c.drawString(100, 95, "Campus Event Management System")
    c.drawRightString(w-100, 95, reg.ticket_code)
    c.save()
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=f"certificate-{reg.ticket_code}.pdf")

@app.route("/admin/dashboard")
@role_required("admin")
def admin_dashboard():
    stats = {
        "users": User.query.count(),
        "events": Event.query.count(),
        "registrations": Registration.query.count(),
        "attendees": Registration.query.filter_by(attended=True).count(),
        "pending_events": Event.query.filter_by(status="pending").count()
    }
    events = Event.query.order_by(Event.created_at.desc()).limit(8).all()
    return render_template("admin/dashboard.html", stats=stats, events=events)

@app.route("/admin/users")
@role_required("admin")
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=users)

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
    events = Event.query.order_by(Event.created_at.desc()).all()
    return render_template("admin/events.html", events=events)

@app.route("/admin/events/<int:event_id>/<action>", methods=["POST"])
@role_required("admin")
def event_action(event_id, action):
    event = Event.query.get_or_404(event_id)
    if action not in ("approve","reject"):
        abort(400)
    event.status = "approved" if action == "approve" else "rejected"
    create_notification(event.organizer_id, f"Event {event.status}", f"{event.title} has been {event.status} by admin.")
    db.session.commit()
    flash(f"Event {event.status}.", "success")
    return redirect(url_for("admin_events"))

@app.route("/admin/registrations")
@role_required("admin")
def admin_registrations():
    registrations = Registration.query.order_by(Registration.registered_at.desc()).all()
    return render_template("admin/registrations.html", registrations=registrations)

@app.route("/admin/reports")
@role_required("admin")
def admin_reports():
    total_revenue = sum(r.event.fee for r in Registration.query.filter_by(payment_status="paid").all())
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
