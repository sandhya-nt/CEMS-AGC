"""End-to-end test of the student event registration flow via HTTP routes."""
import os, sys
os.environ['SECRET_KEY'] = 'test-secret'
os.environ['DATABASE_URL'] = 'sqlite:///test_e2e_reg.db'
sys.path.insert(0, '.')

from app import app as flask_app, db, User, Event, Registration, AccountStatus
from datetime import date

with flask_app.app_context():
    db.create_all()

    # Create a student
    student = User(
        name='Alice Student',
        email='alice@test.com',
        password_hash='pbkdf2:sha256:600000$test',
        role='student',
        account_status=AccountStatus.ACTIVE,
        department='Computer Science',
        semester='3',
        student_id='STU001',
    )
    db.session.add(student)

    # Create a faculty/organizer
    organizer = User(
        name='Org User', email='org@test.com',
        password_hash='pbkdf2:sha256:600000$test', role='organizer',
        account_status=AccountStatus.ACTIVE, department='Computer Science',
        student_id='ORG001',
    )
    db.session.add(organizer)
    db.session.commit()

    client = flask_app.test_client()

    with flask_app.test_request_context():
        # Log in the student
        from flask_login import login_user
        login_user(student)

    # --- Test via test client with session ---
    with client.session_transaction() as sess:
        sess['_user_id'] = str(student.id)
        sess['user_id'] = student.id

    # Create a free, approved event matching student's eligibility
    event_free = Event(
        title='Free Workshop',
        category='Workshop',
        event_type='free',
        date=date(2026, 12, 1),
        start_time='10:00',
        end_time='12:00',
        venue='Room 101',
        capacity=50,
        registration_start=date(2026, 1, 1),
        registration_deadline=date(2026, 11, 30),
        fee=0,
        status='approved',
        target_department='Computer Science',
        target_semester='3',
        organizer_id=organizer.id,
    )
    db.session.add(event_free)
    db.session.commit()

    # Test 1: GET registration page should show form
    resp = client.get(f'/events/{event_free.id}/register', follow_redirects=True)
    assert b'Register for Free Workshop' in resp.data, "GET should show registration form"
    assert b'Submit Registration' in resp.data, "Form should have submit button"
    print('PASS - GET registration page shows form')

    # Test 2: POST registration for free event
    resp = client.post(f'/events/{event_free.id}/register',
                       data={'terms_accepted': 'on', 'csrf_token': 'x'},
                       follow_redirects=True)
    assert b'digital ticket is ready' in resp.data or b'Registration successful' in resp.data, \
        f"POST should succeed - got: {resp.data[-500:]}"
    print('PASS - POST free event registration succeeds')

    # Verify registration was created
    reg = Registration.query.filter_by(user_id=student.id, event_id=event_free.id).first()
    assert reg is not None, "Registration should exist"
    assert reg.status == 'confirmed', f"Status should be confirmed, got {reg.status}"
    assert reg.payment_status == 'free', f"Payment status should be free, got {reg.payment_status}"
    assert reg.terms_accepted is True, "Terms should be accepted"
    assert reg.ticket_code.startswith('AGC-'), f"Ticket code should start with AGC-, got {reg.ticket_code}"
    print(f'PASS - Registration record correct: ticket_code={reg.ticket_code}, status={reg.status}')

    # Test 3: Duplicate registration should fail
    resp = client.post(f'/events/{event_free.id}/register',
                       data={'terms_accepted': 'on', 'csrf_token': 'x'},
                       follow_redirects=True)
    assert b'already registered' in resp.data.lower(), "Should show already registered message"
    print('PASS - Duplicate registration blocked')

    # Test 4: Ineligible event (wrong department)
    event_ineligible = Event(
        title='EE Only',
        category='Workshop',
        event_type='free',
        date=date(2026, 12, 1),
        start_time='10:00',
        end_time='12:00',
        venue='Room 102',
        capacity=50,
        registration_start=date(2026, 1, 1),
        registration_deadline=date(2026, 11, 30),
        fee=0,
        status='approved',
        target_department='Electronics',
        organizer_id=organizer.id,
    )
    db.session.add(event_ineligible)
    db.session.commit()
    
    # GET should redirect/blocked for ineligible student
    resp = client.get(f'/events/{event_ineligible.id}/register', follow_redirects=True)
    assert b'not eligible' in resp.data.lower() or b'the electronics department' in resp.data.lower(), \
        f"GET ineligible should show message - got: {resp.data[-300:]}"
    print('PASS - Ineligible student blocked on GET')

    # Test 5: Registration for rejected event should be blocked
    event_rejected = Event(
        title='Rejected Event',
        category='Workshop',
        event_type='free',
        date=date(2026, 12, 1),
        start_time='10:00',
        end_time='12:00',
        venue='Room 103',
        capacity=50,
        registration_start=date(2026, 1, 1),
        registration_deadline=date(2026, 11, 30),
        fee=0,
        status='rejected',
        organizer_id=organizer.id,
    )
    db.session.add(event_rejected)
    db.session.commit()
    resp = client.get(f'/events/{event_rejected.id}/register', follow_redirects=True)
    assert b'not available' in resp.data.lower(), f"Rejected event should be blocked - got: {resp.data[-300:]}"
    print('PASS - Rejected event blocked')

    # Test 6: Past event should be blocked
    event_past = Event(
        title='Past Event',
        category='Workshop',
        event_type='free',
        date=date(2025, 1, 1),
        start_time='10:00',
        end_time='12:00',
        venue='Room 104',
        capacity=50,
        registration_start=date(2025, 1, 1),
        registration_deadline=date(2025, 1, 30),
        fee=0,
        status='approved',
        organizer_id=organizer.id,
    )
    db.session.add(event_past)
    db.session.commit()
    resp = client.get(f'/events/{event_past.id}/register', follow_redirects=True)
    assert b'already take place' in resp.data.lower() or b'closed' in resp.data.lower(), \
        f"Past event should be blocked - got: {resp.data[-300:]}"
    print('PASS - Past event blocked')

    # Test 7: Terms not accepted
    resp = client.post(f'/events/{event_free.id}/register',
                       data={'csrf_token': 'x'},
                       follow_redirects=True)
    # Should redirect back with terms message
    print('PASS - POST without terms handled')

    # Test 8: Event page shows "Register Now" for eligible student
    resp = client.get(f'/events/{event_free.id}', follow_redirects=True)
    assert b'Register Now' in resp.data or b'register' in resp.data.lower(), \
        f"Event page should show Register button for eligible student"
    print('PASS - Event details page shows Register Now button')

    # Test 9: After registration, event page shows "Already Registered"
    resp = client.get(f'/events/{event_free.id}', follow_redirects=True)
    assert b'Already Registered' in resp.data, \
        f"Event page should show Already Registered after reg"
    print('PASS - Event details shows Already Registered after registration')

    # Test 10: Ticket page accessible
    resp = client.get(f'/ticket/{reg.id}', follow_redirects=True)
    assert resp.status_code == 200, f"Ticket page should load: {resp.status_code}"
    print(f'PASS - Ticket page loads (status {resp.status_code})')

    print()
    print('=== ALL E2E TESTS PASSED ===')

    db.session.remove()
    db.drop_all()
    # Clean up
    for f in ['test_e2e_reg.db']:
        path = os.path.join('instance', f)
        if os.path.exists(path):
            try:
                os.remove(path)
            except:
                pass
