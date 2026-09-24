import sys
import os

os.environ['DATABASE_URL'] = 'sqlite:///test_reg_report.db'
os.environ['SECRET_KEY'] = 'test-secret-key'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, seed_data
from app import User, Event, Registration, EventFaculty

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

client = app.test_client()

# Login first
resp = client.post('/login', data={
    'email': 'teacher@agc.local',
    'password': 'Teacher@123',
    'role': 'teacher'
}, follow_redirects=True)
print(f"Login status: {resp.status_code}")
content = resp.get_data(as_text=True)
print(f"Login page has Welcome: {'Welcome' in content}")
print(f"Login page has Teacher: {'Teacher' in content}")

# Check if user is in session by making authenticated request
resp = client.get('/api/teacher/reports/registration')
print(f"\nAPI status: {resp.status_code}")
print(f"API location: {resp.headers.get('Location', 'none')}")
if resp.status_code in (200, 302):
    data = resp.get_json()
    if data:
        print(f"API success: {data.get('success')}")
        if data.get('success'):
            print(f"Stats: {data.get('stats')}")
            print(f"Empty msg: {data.get('empty_message')}")
        else:
            print(f"Error: {data}")
    else:
        print(f"HTML response: {resp.get_data(as_text=True)[:300]}")

# Try reports page directly
resp = client.get('/teacher/reports', follow_redirects=True)
print(f"\nReports page (follow) status: {resp.status_code}")
content = resp.get_data(as_text=True)
if resp.status_code == 200:
    print(f"Has Reports & Analytics: {'Reports & Analytics' in content}")
    print(f"Has event selector: {'All Assigned Events' in content}")
    print(f"Has summary cards: {'Total Registrations' in content}")
else:
    print(f"Content: {content[:500]}")
