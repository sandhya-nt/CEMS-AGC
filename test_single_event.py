from app import app
import re
import time

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
        
        # Login as organizer
        token = get_csrf('/login')
        resp = client.post('/login', data={
            'email': 'organizer@agc.local',
            'password': 'Organizer@123',
            'csrf_token': token
        }, follow_redirects=True)
        print('Login status:', resp.status_code)
        
        # Create event
        token = get_csrf('/organizer/events/create')
        print('CSRF token obtained:', token is not None)
        
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
        
        print('Create status:', resp.status_code)
        print('Location:', resp.headers.get('Location', 'N/A'))
        
        if resp.status_code == 302:
            print('SUCCESS: Event created')
        else:
            html = resp.data.decode('utf-8')
            print('Response:', html[:500])
        
        # Check database
        from app import Event
        event = Event.query.filter_by(title='Pending Test').first()
        if event:
            print(f'Event found: status={event.status}')
        else:
            print('Event NOT found in database')
            print('Total events:', Event.query.count())
