"""Test registration flow against a real HTTP server using requests library.
Simulates exactly what a browser does with fetch()."""
import os
import re
import sys
import time
import threading

os.environ['DATABASE_URL'] = 'sqlite:///cems_test_http.db'
os.environ['SECRET_KEY'] = 'dev-secret-change-me'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from cems.extensions import limiter

with app.app_context():
    db.drop_all()
    db.create_all()

# Start Flask dev server
def run_server():
    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    app.run(host='127.0.0.1', port=5555, debug=False, use_reloader=False)

t = threading.Thread(target=run_server, daemon=True)
t.start()
time.sleep(2)
print("Server started on http://127.0.0.1:5555")

import requests

def test_registration(url, form_fields, label, with_csrf=True, session=None):
    """Simulate browser: GET page -> extract CSRF -> POST via fetch equivalent."""
    sess = session or requests.Session()

    # GET the page
    resp = sess.get(f'http://127.0.0.1:5555{url}')
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  GET {url}: Status={resp.status_code}")

    csrf_token = None
    if with_csrf:
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', resp.text)
        if match:
            csrf_token = match.group(1)
            print(f"  CSRF token: {csrf_token[:50]}...")
        else:
            print("  WARNING: No CSRF token found!")

    # Build form data like FormData would
    form_data = dict(form_fields)
    if csrf_token:
        form_data['csrf_token'] = csrf_token

    # Simulate fetch(form.action, { method: 'POST', body: formData, headers: {'X-Requested-With': 'XMLHttpRequest'} })
    resp2 = sess.post(f'http://127.0.0.1:5555{url}',
        data=form_data,
        headers={'X-Requested-With': 'XMLHttpRequest'})

    print(f"  POST {url}: Status={resp2.status_code}")
    print(f"  Content-Type: {resp2.headers.get('Content-Type', 'NOT SET')}")
    print(f"  Response body (first 200): {resp2.text[:200]}")

    content_type = resp2.headers.get('Content-Type', '')
    if 'application/json' in content_type:
        print(f"  >>> JSON response: {resp2.json()}")
        print(f"  >>> Frontend handles this correctly")
        return "json"
    else:
        print(f"  >>> NON-JSON response!")
        print(f"  >>> response.json() would THROW SyntaxError")
        print(f"  >>> .catch() shows 'Network error. Please try again.'")
        return "non_json"

# Test 1: Student registration with valid data and valid CSRF
sess1 = requests.Session()
result = test_registration(
    '/register/student',
    {
        'name': 'Browser Test Student',
        'email': 'browserstu@test.com',
        'mobile': '+91 1234567890',
        'student_id': 'STU001',
        'roll_no': 'ROLL001',
        'course': 'B.Tech',
        'semester': '3',
        'academic_session': '2023-2024',
        'section': 'A',
        'department': 'Computer Science',
        'password': 'TestPass123!',
        'confirm_password': 'TestPass123!',
    },
    'Student (valid data, valid CSRF)',
    session=sess1
)

# Test 2: Faculty registration with valid data and valid CSRF
result = test_registration(
    '/register/faculty',
    {
        'name': 'Browser Test Faculty',
        'role': 'faculty',
        'employee_id': 'FAC001',
        'email': 'browserfac@test.com',
        'mobile': '+91 1234567891',
        'department': 'Computer Science',
        'designation': 'Assistant Professor',
        'faculty_role': 'Faculty Member',
        'password': 'TestPass123!',
        'confirm_password': 'TestPass123!',
    },
    'Faculty (valid data, valid CSRF)',
    session=requests.Session()
)

# Test 3: Organizer registration with valid data and valid CSRF
result = test_registration(
    '/register/organizer',
    {
        'name': 'Browser Test Organizer',
        'role': 'organizer',
        'employee_id': 'ORG001',
        'email': 'browserorg@test.com',
        'mobile': '+91 1234567892',
        'department': 'Student Affairs',
        'organizer_name': 'Event Coordinator',
        'event_category': 'General',
        'password': 'TestPass123!',
        'confirm_password': 'TestPass123!',
    },
    'Organizer (valid data, valid CSRF)',
    session=requests.Session()
)

# Test 4: Registration WITHOUT CSRF token (simulates session loss)
print(f"\n{'='*60}")
print(f"  Testing WITHOUT CSRF token (session cookie lost)")
print(f"{'='*60}")
resp = requests.post('http://127.0.0.1:5555/register/student',
    data={
        'name': 'No CSRF Test',
        'email': 'nocSRF@test.com',
        'student_id': 'STU999',
        'roll_no': 'ROLL999',
        'course': 'B.Tech',
        'semester': '3',
        'academic_session': '2023-2024',
        'password': 'TestPass123!',
        'confirm_password': 'TestPass123!',
    },
    headers={'X-Requested-With': 'XMLHttpRequest'},
    allow_redirects=False)
print(f"  POST without CSRF: Status={resp.status_code}")
print(f"  Content-Type: {resp.headers.get('Content-Type')}")
print(f"  Response body: {resp.text[:300]}")
if 'application/json' not in resp.headers.get('Content-Type', ''):
    print(f"  >>> NON-JSON response (CSRF failed)!")
    print(f"  >>> This would show 'Network error' in the browser")

# Test 5: Test with SESSION_COOKIE_SECURE=True (simulating .env)
print(f"\n{'='*60}")
print(f"  Testing WITH SESSION_COOKIE_SECURE=True (HTTPS-only cookie on HTTP)")
print(f"{'='*60}")
app2 = app
app2.config['SESSION_COOKIE_SECURE'] = True

with app2.test_client() as c:
    resp = c.get('/register/student')
    print(f"  GET /register/student: Status={resp.status_code}")
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', resp.get_data(as_text=True))
    csrf = match.group(1) if match else None
    print(f"  CSRF token: {csrf[:50] if csrf else 'NOT FOUND'}...")

    # Note: In test client, SESSION_COOKIE_SECURE=True still sends cookies
    # But in a REAL browser over HTTP, the cookie would NOT be sent
    print(f"  (In a real browser over HTTP, session cookie would NOT be sent with SESSION_COOKIE_SECURE=True)")
    print(f"  (CSRF validation would fail with 'The CSRF session token is missing.')")
    print(f"  (Response would be 400 HTML, causing 'Network error')")

# Test 6: Rate limiting test - hit the limit
print(f"\n{'='*60}")
print(f"  Testing rate limiting (5 per hour including GET)")
print(f"{'='*60}")
# Reset rate limiter storage
try:
    limiter.reset()
except:
    pass

sess3 = requests.Session()
# 1 GET + 5 POSTs = 6 requests, 5th should be rate limited
for i in range(6):
    if i == 0:
        resp = sess3.get('http://127.0.0.1:5555/register/student')
        print(f"  Attempt {i+1} (GET): Status={resp.status_code}")
    else:
        resp = sess3.post('http://127.0.0.1:5555/register/student',
            data={'csrf_token': 'dummy', 'name': 'Rate', 'email': f'rate{i}@test.com'},
            headers={'X-Requested-With': 'XMLHttpRequest'},
            allow_redirects=False)
        ct = resp.headers.get('Content-Type', '')
        print(f"  Attempt {i+1} (POST): Status={resp.status_code}, CT={ct}")
        if resp.status_code == 429:
            print(f"  >>> RATE LIMITED! Response: {resp.text[:150]}")
            print(f"  >>> 429 is HTML, NOT JSON -> response.json() FAILS -> 'Network error'")
            break

print("\nDone! Server shutting down.")
