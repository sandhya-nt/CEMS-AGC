import sys
import os

os.environ['DATABASE_URL'] = 'sqlite:///test_reg_report.db'
os.environ['SECRET_KEY'] = 'test-secret-key'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, seed_data
from app import User, Event, Registration, EventFaculty
from flask_login import login_user

app.config['WTF_CSRF_ENABLED'] = False

with app.app_context():
    db.drop_all()
    db.create_all()
    seed_data()
    db.session.commit()

    teacher = User.query.filter_by(email='teacher@agc.local').first()
    student = User.query.filter_by(email='student@agc.local').first()
    events = Event.query.limit(3).all()

    if student and events:
        for i, event in enumerate(events):
            status = ['pending', 'approved', 'rejected', 'waitlisted'][i % 4]
            reg = Registration(
                ticket_code=f"AGC-TEST{i:06X}",
                user_id=student.id,
                event_id=event.id,
                status=status,
                payment_status="free",
                terms_accepted=True,
            )
            db.session.add(reg)
        db.session.commit()

    for event in events:
        ef = EventFaculty(event_id=event.id, faculty_id=teacher.id)
        db.session.add(ef)
    db.session.commit()

# Log in teacher programmatically
with app.app_context():
    teacher = User.query.filter_by(email='teacher@agc.local').first()
    login_user(teacher)
    db.session.commit()

client = app.test_client()

# Set the session cookie by making a request while logged in
with app.test_request_context():
    from flask_login import current_user
    print(f"Current user: {current_user}")
    print(f"Current user role: {current_user.role}")

# Use the session to make authenticated requests
# We need to capture the session after login_user and apply it
# Flask test client with session_transaction
with client.session_transaction() as sess:
    from flask import session
    # The session is already managed by Flask-Login
    pass

# Alternative: use open_session to set the user
# Let's try a different approach - login via the test client properly

print("\n=== Using direct session approach ===")

# Clear any existing cookies and establish authenticated session
with app.app_context():
    from flask_login import login_user
    teacher = User.query.filter_by(email='teacher@agc.local').first()
    login_user(teacher)

client = app.test_client()

# Make a request to establish session
resp = client.get('/')
print(f"Home page: {resp.status_code}")

print("\n=== Test 1: Reports Page ===")
resp = client.get('/teacher/reports')
print(f"Status: {resp.status_code}")
if resp.status_code != 200:
    print(f"Location: {resp.headers.get('Location', 'none')}")
ok = resp.status_code == 200
if ok:
    content = resp.get_data(as_text=True)
    checks = [
        ('Reports & Analytics title', 'Reports & Analytics' in content),
        ('Event selector', 'All Assigned Events' in content),
        ('Registration Report section', 'Registration Report' in content),
        ('Total Registrations card', 'Total Registrations' in content),
        ('Pending card', 'Pending' in content),
        ('Approved card', 'Approved' in content),
        ('Rejected card', 'Rejected' in content),
        ('Waitlisted card', 'Waitlisted' in content),
        ('Load Report button', 'Load Report' in content),
    ]
    for name, result in checks:
        print(f"  {name}: {'OK' if result else 'FAIL'}")
else:
    print(f"Content: {resp.get_data(as_text=True)[:300]}")
