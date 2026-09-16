from app import app
import re
import time

results = []

with app.app_context():
    with app.test_client() as client:
        def get_csrf(path):
            time.sleep(1)
            resp = client.get(path)
            html = resp.data.decode('utf-8')
            match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html, re.DOTALL)
            if not match:
                return None
            return match.group(1)
        
        def login(email, password):
            time.sleep(1)
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
            time.sleep(1)
        
        # Test 1: Organizer creates event as draft
        if login('organizer@agc.local', 'Organizer@123'):
            token = get_csrf('/organizer/events/create')
            if token:
                resp = client.post('/organizer/events/create', data={
                    'title': 'Draft Test',
                    'category': 'Technical',
                    'event_type': 'free',
                    'date': '2026-12-01',
                    'start_time': '10:00 AM',
                    'end_time': '12:00 PM',
                    'venue': 'Seminar Hall',
                    'capacity': '50',
                    'fee': '0',
                    'description': 'Draft',
                    'highlights': 'Test',
                    'rules': 'Test',
                    'eligibility': 'Test',
                    'contact_info': 'test@test.com',
                    'main_guest': '',
                    'chief_guest': '',
                    'action': 'draft',
                    'csrf_token': token
                }, follow_redirects=False)
                results.append(f'Draft creation: {resp.status_code}')
            logout()
        
        time.sleep(2)
        
        # Test 2: Organizer submits event
        if login('organizer@agc.local', 'Organizer@123'):
            token = get_csrf('/organizer/events/create')
            if token:
                resp = client.post('/organizer/events/create', data={
                    'title': 'Pending Test',
                    'category': 'Technical',
                    'event_type': 'free',
                    'date': '2026-12-02',
                    'start_time': '10:00 AM',
                    'end_time': '12:00 PM',
                    'venue': 'Seminar Hall',
                    'capacity': '50',
                    'fee': '0',
                    'description': 'Pending',
                    'highlights': 'Test',
                    'rules': 'Test',
                    'eligibility': 'Test',
                    'contact_info': 'test@test.com',
                    'main_guest': '',
                    'chief_guest': '',
                    'action': 'submit',
                    'csrf_token': token
                }, follow_redirects=False)
                results.append(f'Submit creation: {resp.status_code}')
            logout()
        
        time.sleep(2)
        
        # Test 3: Admin approves pending event
        if login('admin@agc.local', 'Admin@123'):
            resp = client.get('/admin/events')
            html = resp.data.decode('utf-8')
            
            # Find approve form
            match = re.search(r'/admin/events/(\d+)/approve"', html)
            if match:
                event_id = match.group(1)
                csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html, re.DOTALL)
                csrf_token = csrf_match.group(1) if csrf_match else ''
                
                resp = client.post(f'/admin/events/{event_id}/approve', data={
                    'csrf_token': csrf_token
                }, follow_redirects=False)
                results.append(f'Admin approve: {resp.status_code}')
            else:
                results.append('FAIL: No approve form found')
            logout()
        
        time.sleep(2)
        
        # Test 4: Check event statuses
        from app import Event
        pending = Event.query.filter_by(status='pending').count()
        approved = Event.query.filter_by(status='approved').count()
        draft = Event.query.filter_by(status='draft').count()
        waiting = Event.query.filter_by(status='waiting').count()
        results.append(f'Status counts - pending:{pending} approved:{approved} draft:{draft} waiting:{waiting}')
        
        # Test 5: Student sees only approved events
        if login('student@agc.local', 'Student@123'):
            resp = client.get('/events')
            html = resp.data.decode('utf-8')
            
            # Count event cards
            event_cards = html.count('cems-event-card')
            results.append(f'Student sees {event_cards} event cards')
            
            # Check that pending/draft events are NOT visible
            if 'Pending Test' not in html:
                results.append('PASS: Pending event hidden from student')
            else:
                results.append('FAIL: Pending event visible to student')
            logout()
        
        time.sleep(2)
        
        # Test 6: Reject flow
        if login('organizer@agc.local', 'Organizer@123'):
            token = get_csrf('/organizer/events/create')
            if token:
                client.post('/organizer/events/create', data={
                    'title': 'Reject Test',
                    'category': 'Technical',
                    'event_type': 'free',
                    'date': '2026-12-03',
                    'start_time': '10:00 AM',
                    'end_time': '12:00 PM',
                    'venue': 'Seminar Hall',
                    'capacity': '50',
                    'fee': '0',
                    'description': 'Reject',
                    'highlights': 'Test',
                    'rules': 'Test',
                    'eligibility': 'Test',
                    'contact_info': 'test@test.com',
                    'main_guest': '',
                    'chief_guest': '',
                    'action': 'submit',
                    'csrf_token': token
                }, follow_redirects=False)
            logout()
        
        time.sleep(2)
        
        if login('admin@agc.local', 'Admin@123'):
            resp = client.get('/admin/events')
            html = resp.data.decode('utf-8')
            
            # Find reject form
            match = re.search(r'/admin/events/(\d+)/reject"', html)
            if match:
                event_id = match.group(1)
                csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html, re.DOTALL)
                csrf_token = csrf_match.group(1) if csrf_match else ''
                
                resp = client.post(f'/admin/events/{event_id}/reject', data={
                    'csrf_token': csrf_token,
                    'rejection_reason': 'Not ready'
                }, follow_redirects=False)
                results.append(f'Admin reject: {resp.status_code}')
                
                # Verify status
                event = Event.query.get(event_id)
                if event and event.status == 'rejected':
                    results.append('PASS: Event rejected successfully')
                else:
                    results.append(f'FAIL: Event status is {event.status if event else "not found"}')
            else:
                results.append('FAIL: No reject form found')
            logout()

print('\n'.join(results))
