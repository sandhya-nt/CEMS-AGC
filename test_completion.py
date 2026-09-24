from app import app, db, Event, EventFaculty, User, Registration

def get_csrf(client):
    import re
    rv = client.get('/login')
    m = re.search(r'name="csrf_token" value="([^"]+)"', rv.data.decode())
    return m.group(1) if m else ''

def login(client, email, password):
    csrf = get_csrf(client)
    rv = client.post('/login', data={'email': email, 'password': password, 'csrf_token': csrf}, follow_redirects=True)
    return rv.status_code == 200

with app.test_client() as client:
    errors = []
    checks = []

    # 1. Login as teacher
    if login(client, 'teacher@agc.local', 'Teacher@123'):
        checks.append(('Teacher login', True))
    else:
        errors.append('Teacher login failed')
        checks.append(('Teacher login', False))

    # 2. Dashboard - check key content
    rv = client.get('/teacher/dashboard', follow_redirects=True)
    content = rv.data.decode()
    if 'Welcome' in content and 'Teacher' in content:
        checks.append(('Dashboard renders', True))
    else:
        errors.append('Dashboard content wrong')
        checks.append(('Dashboard renders', False))

    # 3. Completed events page
    rv = client.get('/faculty/completed-events', follow_redirects=True)
    if rv.status_code == 200 and 'Completed Events' in rv.data.decode():
        checks.append(('Completed events page', True))
    else:
        errors.append('Completed events page failed: %s' % rv.status_code)
        checks.append(('Completed events page', False))

    # 4. Completion form for approved event
    event = Event.query.filter_by(status='approved').first()
    if event:
        rv = client.get('/faculty/event/%d/complete' % event.id, follow_redirects=True)
        if rv.status_code == 200:
            checks.append(('Completion form page', True))
        else:
            errors.append('Completion form failed: %s' % rv.status_code)
            checks.append(('Completion form page', False))

        # Check checklist or confirmation content
        content = rv.data.decode()
        has_checklist = 'Checklist' in content or 'complete' in content.lower()
        if has_checklist:
            checks.append(('Completion checklist content', True))
        else:
            errors.append('Completion checklist content missing')
            checks.append(('Completion checklist content', False))

        # 5. Student security
        client.get('/logout')
        login(client, 'student@agc.local', 'Student@123')
        rv = client.get('/faculty/event/%d/complete' % event.id)
        if rv.status_code == 403:
            checks.append(('Student blocked (403)', True))
        else:
            errors.append('Student got %s instead of 403' % rv.status_code)
            checks.append(('Student blocked (403)', False))

        rv = client.get('/faculty/completed-events')
        if rv.status_code == 403:
            checks.append(('Student events blocked (403)', True))
        else:
            errors.append('Student events got %s instead of 403' % rv.status_code)
            checks.append(('Student events blocked (403)', False))

        # 6. Report/summary for non-completed event
        client.get('/logout')
        login(client, 'teacher@agc.local', 'Teacher@123')
        rv = client.get('/faculty/event/%d/summary' % event.id, follow_redirects=True)
        content = rv.data.decode()
        has_warning = 'completed' in content.lower() and ('not' in content.lower() or 'yet' in content.lower() or 'already' in content.lower())
        if rv.status_code == 200 and has_warning:
            checks.append(('Summary warning', True))
        else:
            errors.append('Summary warning missing: %s' % rv.status_code)
            checks.append(('Summary warning', False))

        rv = client.get('/faculty/event/%d/report?format=pdf' % event.id, follow_redirects=True)
        content = rv.data.decode()
        has_warning2 = 'completed' in content.lower() and ('not' in content.lower() or 'yet' in content.lower() or 'already' in content.lower())
        if rv.status_code == 200 and has_warning2:
            checks.append(('Report warning', True))
        else:
            errors.append('Report warning missing: %s' % rv.status_code)
            checks.append(('Report warning', False))

        # 7. Report for completed event - mark one as completed
        event.status = 'completed'
        from datetime import datetime
        event.completed_at = datetime.utcnow()
        event.completed_by = User.query.filter_by(role='teacher').first().id
        db.session.commit()

        rv = client.get('/faculty/event/%d/summary' % event.id, follow_redirects=True)
        if rv.status_code == 200:
            checks.append(('Summary for completed event', True))
        else:
            errors.append('Summary for completed event failed: %s' % rv.status_code)
            checks.append(('Summary for completed event', False))

        rv = client.get('/faculty/completed-events', follow_redirects=True)
        content = rv.data.decode()
        if event.title in content:
            checks.append(('Completed event listed', True))
        else:
            errors.append('Completed event not listed')
            checks.append(('Completed event listed', False))

        rv = client.get('/faculty/event/%d/report?format=pdf' % event.id, follow_redirects=True)
        if rv.status_code == 200 and len(rv.data) > 100:
            checks.append(('Report for completed event', True))
        else:
            errors.append('Report for completed event failed: %s' % rv.status_code)
            checks.append(('Report for completed event', False))

    else:
        errors.append('No approved event found')

    # Summary
    print('\n=== TEST RESULTS ===')
    for name, result in checks:
        status = 'PASS' if result else 'FAIL'
        print('%s: %s' % (status, name))

    if errors:
        print('\n=== ERRORS ===')
        for e in errors:
            print('FAIL: %s' % e)
    else:
        print('\n=== ALL COMPLETION MODULE TESTS PASSED ===')
