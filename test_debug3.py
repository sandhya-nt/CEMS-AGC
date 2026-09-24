from app import app, db, Event, EventFaculty, User, Registration
from datetime import datetime

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
    # 1. Login as teacher
    if login(client, 'teacher@agc.local', 'Teacher@123'):
        print('PASS: Teacher login')
    else:
        print('FAIL: Teacher login')

    # 2. Check dashboard content
    rv = client.get('/teacher/dashboard', follow_redirects=True)
    content = rv.data.decode()
    print('Dashboard status:', rv.status_code)
    print('Has Welcome:', 'Welcome' in content)
    if 'Welcome' in content:
        print('Welcome context:', content[content.find('Welcome')-20:content.find('Welcome')+50])

    # 3. Check summary route for non-completed event
    event = Event.query.filter_by(status='approved').first()
    if event:
        rv = client.get('/faculty/event/%d/summary' % event.id, follow_redirects=True)
        content = rv.data.decode()
        print('\nSummary status:', rv.status_code)
        # Print if it has any completion-related text
        for word in ['completed', 'complete', 'finish', 'finalize', 'not', 'yet', 'already']:
            if word.lower() in content.lower():
                idx = content.lower().find(word.lower())
                print('Has "%s":' % word, 'YES - context:', content[max(0,idx-30):idx+80])
                break
        else:
            print('No completion words found')
            print('Content length:', len(content))
            if content:
                print('First 300 chars:', content[:300])
