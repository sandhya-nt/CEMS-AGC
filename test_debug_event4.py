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
        print('Location:', resp.headers.get('Location', 'N/A'))
        
        # Check database immediately
        from app import Event, db
        db.session.expire_all()
        event = Event.query.filter_by(title='Pending Test').first()
        if event:
            print(f'Event found: status={event.status}')
        else:
            print('Event NOT found immediately after creation')
            print('Total events:', Event.query.count())
            
            # List recent events
            recent = Event.query.order_by(Event.id.desc()).limit(5).all()
            for e in recent:
                print(f'  Event {e.id}: {e.title} | status={e.status}')
