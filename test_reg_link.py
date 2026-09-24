import os
os.environ['TESTING'] = '1'
from app import app
import re

with app.app_context():
    from app import db, Event, User
    event = Event.query.filter(Event.title.ilike('%Coding%')).first()
    event_id = event.id
    student = User.query.filter_by(email='student@agc.local').first()

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['_user_id'] = str(student.id)

    resp1 = client.get(f'/events/{event_id}')
    body1 = resp1.data.decode('utf-8')

    # Find all occurrences of "Register" 
    for match in re.finditer(r'Register', body1):
        start = max(0, match.start() - 100)
        end = min(len(body1), match.end() + 150)
        context = body1[start:end]
        print(f"--- Found at position {match.start()} ---")
        print(context)
        print()
