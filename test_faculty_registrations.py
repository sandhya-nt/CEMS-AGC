import sys
sys.path.insert(0, '.')
from app import app, db, EventFaculty, User, Event
from cems.services import available_seats

with app.app_context():
    print("Test 1: App loads - PASS")
    app.config['WTF_CSRF_ENABLED'] = False
    client = app.test_client()
    resp = client.post('/api/login', json={'email': 'teacher@agc.local', 'password': 'Teacher@123', 'role': 'teacher'})
    print(f"Test 2 Login: status={resp.status_code} raw={resp.get_data(as_text=True)[:200]}")

    # Test manage registrations page
    resp = client.get('/teacher/registrations/manage')
    print(f"Test 3 Manage page: status={resp.status_code}")

    # Test API registrations endpoint (without auth - should fail)
    resp = client.get('/api/teacher/registrations')
    print(f"Test 4 API no auth: status={resp.status_code}")

    # Now login and try again
    client.post('/api/login', json={'email': 'teacher@agc.local', 'password': 'Teacher@123', 'role': 'teacher'})
    resp = client.get('/api/teacher/registrations')
    data = resp.get_json()
    print(f"Test 5 API with auth: status={resp.status_code} success={data.get('success')} count={len(data.get('registrations', []))}")

    # Check teacher assignments
    teacher = User.query.filter_by(email='teacher@agc.local').first()
    if teacher:
        print(f"Test 6 Teacher found: {teacher.name} (ID: {teacher.id})")
        assignments = EventFaculty.query.filter_by(faculty_id=teacher.id).all()
        print(f"Test 7 EventFaculty assignments: {len(assignments)}")
        for a in assignments:
            event = Event.query.get(a.event_id)
            print(f"  -> Event: {event.title if event else 'N/A'} (ID: {a.event_id})")

        organized = Event.query.filter_by(organizer_id=teacher.id).all()
        print(f"Test 8 Teacher organized events: {len(organized)}")
        for e in organized:
            print(f"  -> {e.title} (ID: {e.id})")

    print("ALL TESTS COMPLETE")
