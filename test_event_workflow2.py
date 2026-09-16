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
        
        # Test admin approval flow
        print("Test: Admin approves pending event")
        if login('admin@agc.local', 'Admin@123'):
            resp = client.get('/admin/events')
            html = resp.data.decode('utf-8')
            
            # Find pending event
            match = re.search(r'/admin/events/(\d+)/approve', html)
            if match:
                event_id = match.group(1)
                # Get CSRF from the events page
                csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html, re.DOTALL)
                csrf_token = csrf_match.group(1) if csrf_match else ''
                
                resp = client.post(f'/admin/events/{event_id}/approve', data={
                    'csrf_token': csrf_token
                }, follow_redirects=False)
                
                if resp.status_code == 302:
                    results.append(f'PASS: Admin approved event {event_id}')
                else:
                    results.append(f'FAIL: Admin approval - status {resp.status_code}')
            else:
                results.append('FAIL: No pending event found')
            logout()
        else:
            results.append('FAIL: Admin login failed')
        
        time.sleep(1)
        
        # Test admin rejection flow
        print("Test: Admin rejects pending event")
        if login('admin@agc.local', 'Admin@123'):
            # First create a new pending event
            if login('organizer@agc.local', 'Organizer@123'):
                token = get_csrf('/organizer/events/create')
                if token:
                    client.post('/organizer/events/create', data={
                        'title': 'Test Reject Event',
                        'category': 'Technical',
                        'event_type': 'free',
                        'date': '2026-12-03',
                        'start_time': '10:00 AM',
                        'end_time': '12:00 PM',
                        'venue': 'Seminar Hall',
                        'capacity': '50',
                        'fee': '0',
                        'description': 'Test reject event',
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
            
            time.sleep(1)
            
            # Now reject it as admin
            resp = client.get('/admin/events')
            html = resp.data.decode('utf-8')
            
            # Find the new pending event
            match = re.search(r'/admin/events/(\d+)/reject', html)
            if match:
                event_id = match.group(1)
                csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html, re.DOTALL)
                csrf_token = csrf_match.group(1) if csrf_match else ''
                
                resp = client.post(f'/admin/events/{event_id}/reject', data={
                    'csrf_token': csrf_token,
                    'rejection_reason': 'Not enough details'
                }, follow_redirects=False)
                
                if resp.status_code == 302:
                    results.append(f'PASS: Admin rejected event {event_id}')
                else:
                    results.append(f'FAIL: Admin rejection - status {resp.status_code}')
            else:
                results.append('FAIL: No rejectable event found')
            logout()
        else:
            results.append('FAIL: Admin login failed')
        
        time.sleep(1)
        
        # Test waiting status for changes
        print("Test: Change approval flow (waiting status)")
        # Create and approve an event first
        if login('organizer@agc.local', 'Organizer@123'):
            token = get_csrf('/organizer/events/create')
            if token:
                client.post('/organizer/events/create', data={
                    'title': 'Test Change Event',
                    'category': 'Technical',
                    'event_type': 'free',
                    'date': '2026-12-04',
                    'start_time': '10:00 AM',
                    'end_time': '12:00 PM',
                    'venue': 'Seminar Hall',
                    'capacity': '50',
                    'fee': '0',
                    'description': 'Test change event',
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
        
        time.sleep(1)
        
        # Approve it as admin
        if login('admin@agc.local', 'Admin@123'):
            resp = client.get('/admin/events')
            html = resp.data.decode('utf-8')
            match = re.search(r'/admin/events/(\d+)/approve', html)
            if match:
                event_id = match.group(1)
                csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html, re.DOTALL)
                csrf_token = csrf_match.group(1) if csrf_match else ''
                client.post(f'/admin/events/{event_id}/approve', data={
                    'csrf_token': csrf_token
                }, follow_redirects=False)
                results.append(f'PASS: Approved event {event_id} for change test')
            else:
                results.append('FAIL: No event to approve for change test')
            logout()
        
        time.sleep(1)
        
        # Now edit the event as organizer to trigger waiting status
        if login('organizer@agc.local', 'Organizer@123'):
            # Get the event ID
            from app import Event
            event = Event.query.filter_by(title='Test Change Event').first()
            if event:
                token = get_csrf(f'/organizer/events/{event.id}/manage')
                if token:
                    resp = client.post(f'/organizer/events/{event.id}/manage', data={
                        'title': 'Test Change Event',
                        'category': 'Technical',
                        'venue': 'Main Auditorium',  # Changed venue
                        'date': '2026-12-04',
                        'registration_deadline': '2026-12-01',
                        'start_time': '10:00 AM',
                        'end_time': '12:00 PM',
                        'capacity': '60',
                        'description': 'Updated description',
                        'highlights': 'Test',
                        'rules': 'Test',
                        'eligibility': 'Test',
                        'contact_info': 'test@test.com',
                        'main_guest': '',
                        'chief_guest': '',
                        'csrf_token': token
                    }, follow_redirects=False)
                    
                    if resp.status_code == 302:
                        results.append('PASS: Organizer edited approved event')
                    else:
                        results.append(f'FAIL: Edit approved event - status {resp.status_code}')
                    
                    # Check event status
                    event = Event.query.get(event.id)
                    results.append(f'Event status after edit: {event.status}')
                    if event.status == 'waiting':
                        results.append('PASS: Event status is waiting after important change')
                    else:
                        results.append(f'FAIL: Expected waiting, got {event.status}')
                else:
                    results.append('FAIL: No CSRF token for manage event')
            else:
                results.append('FAIL: Test Change Event not found')
            logout()
        else:
            results.append('FAIL: Organizer login failed')
        
        time.sleep(1)
        
        # Admin approves the change
        if login('admin@agc.local', 'Admin@123'):
            resp = client.get('/admin/events')
            html = resp.data.decode('utf-8')
            match = re.search(r'/admin/events/(\d+)/approve_change', html)
            if match:
                event_id = match.group(1)
                csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html, re.DOTALL)
                csrf_token = csrf_match.group(1) if csrf_match else ''
                
                resp = client.post(f'/admin/events/{event_id}/approve_change', data={
                    'csrf_token': csrf_token
                }, follow_redirects=False)
                
                if resp.status_code == 302:
                    results.append(f'PASS: Admin approved event change {event_id}')
                else:
                    results.append(f'FAIL: Admin change approval - status {resp.status_code}')
                
                # Verify status
                event = Event.query.get(event_id)
                results.append(f'Event status after change approval: {event.status}')
                if event.status == 'approved':
                    results.append('PASS: Event is approved after change approval')
                else:
                    results.append(f'FAIL: Expected approved, got {event.status}')
            else:
                results.append('FAIL: No waiting event found for change approval')
            logout()
        
        time.sleep(1)
        
        # Test reject change flow
        print("Test: Reject change flow")
        if login('organizer@agc.local', 'Organizer@123'):
            event = Event.query.filter_by(title='Test Change Event').first()
            if event:
                token = get_csrf(f'/organizer/events/{event.id}/manage')
                if token:
                    # Change venue back
                    client.post(f'/organizer/events/{event.id}/manage', data={
                        'title': 'Test Change Event',
                        'category': 'Technical',
                        'venue': 'Seminar Hall',  # Changed back
                        'date': '2026-12-04',
                        'registration_deadline': '2026-12-01',
                        'start_time': '10:00 AM',
                        'end_time': '12:00 PM',
                        'capacity': '60',
                        'description': 'Updated description again',
                        'highlights': 'Test',
                        'rules': 'Test',
                        'eligibility': 'Test',
                        'contact_info': 'test@test.com',
                        'main_guest': '',
                        'chief_guest': '',
                        'csrf_token': token
                    }, follow_redirects=False)
                logout()
        
        time.sleep(1)
        
        if login('admin@agc.local', 'Admin@123'):
            resp = client.get('/admin/events')
            html = resp.data.decode('utf-8')
            match = re.search(r'/admin/events/(\d+)/reject_change', html)
            if match:
                event_id = match.group(1)
                csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html, re.DOTALL)
                csrf_token = csrf_match.group(1) if csrf_match else ''
                
                resp = client.post(f'/admin/events/{event_id}/reject_change', data={
                    'csrf_token': csrf_token
                }, follow_redirects=False)
                
                if resp.status_code == 302:
                    results.append(f'PASS: Admin rejected event change {event_id}')
                else:
                    results.append(f'FAIL: Admin change rejection - status {resp.status_code}')
                
                event = Event.query.get(event_id)
                results.append(f'Event status after change rejection: {event.status}')
                if event.status == 'approved':
                    results.append('PASS: Event reverted to approved after change rejection')
                else:
                    results.append(f'FAIL: Expected approved, got {event.status}')
            else:
                results.append('FAIL: No waiting event found for change rejection')
            logout()

print('\n'.join(results))
