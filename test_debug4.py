from app import app, db, Event

def get_csrf(client):
    import re
    rv = client.get('/login')
    m = re.search(r'name="csrf_token" value="([^"]+)"', rv.data.decode())
    return m.group(1) if m else ''

with app.test_client() as client:
    csrf = get_csrf(client)
    rv = client.post('/login', data={'email': 'teacher@agc.local', 'password': 'Teacher@123', 'csrf_token': csrf}, follow_redirects=True)
    print('Login status:', rv.status_code)
    
    rv = client.get('/teacher/dashboard', follow_redirects=True)
    content = rv.data.decode()
    print('Dashboard status:', rv.status_code)
    print('Has "Welcome,":', 'Welcome,' in content)
    print('Has "Assigned Events":', 'Assigned Events' in content)
    print('Has "Completed Events":', 'Completed Events' in content)
    print('Has "Total Assigned Events":', 'Total Assigned Events' in content)
    
    # Find any Welcome text
    for word in ['Welcome', 'Teacher', 'Dashboard', 'Assigned', 'Completed', 'Assigned Events']:
        if word in content:
            idx = content.find(word)
            print('Has "%s" at %d: ...%s...' % (word, idx, content[max(0,idx-10):idx+60]))
