from app import app
import re

with app.test_client() as client:
    rv = client.get('/login')
    content = rv.data.decode()
    m = re.search(r'name="csrf_token" value="([^"]+)"', content)
    csrf = m.group(1) if m else ''
    
    rv = client.post('/login', data={'email': 'teacher@agc.local', 'password': 'Teacher@123', 'csrf_token': csrf}, follow_redirects=True)
    print('Login status:', rv.status_code)
    
    # Check cookies/session
    cookies = client._cookies
    print('Cookies:', list(cookies.keys()) if hasattr(cookies, 'keys') else 'N/A')
    
    rv = client.get('/teacher/dashboard')
    print('Dashboard status:', rv.status_code)
    if rv.status_code == 302:
        print('Redirect to:', rv.headers.get('Location'))
    
    # Check if user is authenticated
    with client.session_transaction() as sess:
        print('Session user_id:', sess.get('user_id'))
        print('Session _fresh:', sess.get('_fresh'))
        print('Session remember:', sess.get('remember'))
    
    rv = client.get('/teacher/dashboard', follow_redirects=True)
    print('Dashboard (follow) status:', rv.status_code)
    content = rv.data.decode()
    print('Has Welcome:', 'Welcome' in content)
