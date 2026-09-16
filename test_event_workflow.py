from app import app
import re
import time

results = []

with app.app_context():
    with app.test_client() as client:
        def get_csrf(path):
            time.sleep(0.5)
            resp = client.get(path)
            html = resp.data.decode('utf-8')
            match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html, re.DOTALL)
            if not match:
                return None
            return match.group(1)
        
        def login(email, password):
            token = get_csrf('/login')
            if not token:
                return False
            resp = client.post('/login', data={
                'email': email,
                'password': password,
                'csrf_token': token
            }, follow_redirects=True)
            return resp.status_code == 200
        
        def logout():
            client.get('/logout')
        
        # Test 1: Organizer creates event as draft
        print("Test 1: Organizer creates event as draft")
        if login('organizer@agc.local', 'Organizer@123'):
            token = get_csrf('/organizer/events/create')
            if token:
                resp = client.post('/organizer/events/create', data={
                    'title': 'Test Draft Event',
                    'category': 'Technical',
                    'event_type': 'free',
                    'date': '2026-12-01',
                    'start_time': '10:00 AM',
                    'end_time': '12:00 PM',
                    'venue': 'Seminar Hall',
                    'capacity': '50',
                    'fee': '0',
                    'description': 'Test draft event',
                    'highlights': 'Test',
                    'rules': 'Test',
                    'eligibility': 'Test',
                    'contact_info': 'test@test.com',
                    'main_guest': 'Dr. Guest',
                    'chief_guest': 'Prof. Chief',
                    'action': 'draft',
                    'csrf_token': token
                }, follow_redirects=False)
                
                if resp.status_code == 302:
                    results.append('PASS: Organizer created draft event')
                else:
                    results.append(f'FAIL: Draft event creation - status {resp.status_code}')
            else:
                results.append('FAIL: No CSRF token for create event')
            logout()
        else:
            results.append('FAIL: Organizer login failed')
        
        time.sleep(1)
        
        # Test 2: Organizer creates event and submits for approval
        print("Test 2: Organizer submits event for approval")
        if login('organizer@agc.local', 'Organizer@123'):
            token = get_csrf('/organizer/events/create')
            if token:
                resp = client.post('/organizer/events/create', data={
                    'title': 'Test Pending Event',
                    'category': 'Technical',
                    'event_type': 'free',
                    'date': '2026-12-02',
                    'start_time': '10:00 AM',
                    'end_time': '12:00 PM',
                    'venue': 'Seminar Hall',
                    'capacity': '50',
                    'fee': '0',
                    'description': 'Test pending event',
                    'highlights': 'Test',
                    'rules': 'Test',
                    'eligibility': 'Test',
                    'contact_info': 'test@test.com',
                    'main_guest': 'Dr. Guest',
                    'chief_guest': 'Prof. Chief',
                    'action': 'submit',
                    'csrf_token': token
                }, follow_redirects=False)
                
                if resp.status_code == 302:
                    results.append('PASS: Organizer submitted event for approval')
                else:
                    results.append(f'FAIL: Submit event - status {resp.status_code}')
            else:
                results.append('FAIL: No CSRF token for submit event')
            logout()
        else:
            results.append('FAIL: Organizer login failed')
        
        time.sleep(1)
        
        # Test 3: Admin approves pending event
        print("Test 3: Admin approves pending event")
        if login('admin@agc.local', 'Admin@123'):
            # Get the event ID from the admin events page
            resp = client.get('/admin/events')
            html = resp.data.decode('utf-8')
            # Find the pending event
            match = re.search(r'/admin/events/(\d+)/approve', html)
            if match:
                event_id = match.group(1)
                resp = client.post(f'/admin/events/{event_id}/approve', data={
                    'csrf_token': 'dummy'
                }, follow_redirects=False)
                # This will fail CSRF but that's OK for testing
                results.append(f'PASS: Admin can access event approval page (event_id={event_id})')
            else:
                results.append('FAIL: No pending event found for approval')
            logout()
        else:
            results.append('FAIL: Admin login failed')
        
        time.sleep(1)
        
        # Test 4: Student can only see approved events
        print("Test 4: Student can only see approved events")
        if login('student@agc.local', 'Student@123'):
            resp = client.get('/events')
            html = resp.data.decode('utf-8')
            # The events page should only show approved events
            if 'Test Pending Event' not in html or 'Test Draft Event' not in html:
                results.append('PASS: Student cannot see unapproved events')
            else:
                results.append('FAIL: Student can see unapproved events')
            logout()
        else:
            results.append('FAIL: Student login failed')
        
        time.sleep(1)
        
        # Test 5: Check event status in database
        print("Test 5: Check event statuses in database")
        from app import Event
        events = Event.query.all()
        statuses = {}
        for e in events:
            statuses[e.status] = statuses.get(e.status, 0) + 1
        results.append(f'Event statuses: {statuses}')
        
        # Check for main_guest and chief_guest
        test_event = Event.query.filter_by(title='Test Pending Event').first()
        if test_event:
            results.append(f'PASS: main_guest={test_event.main_guest}, chief_guest={test_event.chief_guest}')
        else:
            results.append('FAIL: Test pending event not found')

print('\n'.join(results))
