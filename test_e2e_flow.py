import os
os.environ['TESTING'] = '1'
from app import app

with app.app_context():
    from app import db, Event, User
    event = Event.query.filter(Event.title.ilike('%Coding%')).first()
    event_id = event.id
    student = User.query.filter_by(email='student@agc.local').first()

# Test: Click Register Now → should go to /register/<id> which renders the form
with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['_user_id'] = str(student.id)
    
    # Step 1: Get event details page
    resp1 = client.get(f'/events/{event_id}')
    body1 = resp1.data.decode('utf-8')
    
    # Find the Register Now link
    import re
    reg_match = re.search(r'href="(/register/\d+)"[^>]*>Register Now', body1)
    if reg_match:
        reg_url = reg_match.group(1)
        print(f'Register Now link: {reg_url}')
        
        # Step 2: Follow to registration page
        resp2 = client.get(reg_url)
        body2 = resp2.data.decode('utf-8')
        print(f'Registration page status: {resp2.status_code}')
        print(f'Registration form present: {"Register" in body2 or "register" in body2.lower()}')
        print(f'Event title on reg page: {event.title in body2}')
    else:
        print('ERROR: Could not find Register Now link')
        # Show relevant portion
        idx = body1.find('cta-btn')
        if idx >= 0:
            print(body1[max(0,idx-50):idx+300])
