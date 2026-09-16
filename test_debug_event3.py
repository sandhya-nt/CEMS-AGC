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
        client.post('/login', data={
            'email': 'organizer@agc.local',
            'password': 'Organizer@123',
            'csrf_token': token
        }, follow_redirects=True)
        
        # Create event
        token = get_csrf('/organizer/events/create')
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
        
        print('Status:', resp.status_code)
        
        if resp.status_code == 200:
            html = resp.data.decode('utf-8')
            if 'Could not create event' in html:
                print('ERROR MESSAGE FOUND')
                match = re.search(r'Could not create event: (.+?)\.', html)
                if match:
                    print('Error:', match.group(1))
            else:
                print('No error message - checking for exceptions')
        elif resp.status_code == 302:
            print('Redirect:', resp.headers.get('Location'))
        else:
            print('Unexpected status')
