"""Definitive test: rate limiting with valid CSRF tokens."""
import os, re, sys, time, threading

os.environ['DATABASE_URL'] = 'sqlite:///cems_test_rl.db'
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
    app.run(host='127.0.0.1', port=5556, debug=False, use_reloader=False)

t = threading.Thread(target=run_server, daemon=True)
t.start()
time.sleep(2)
print("Server started on http://127.0.0.1:5556")

import requests

sess = requests.Session()

# Test: Hit rate limit on /register/student with valid CSRF
# Rate limit is 5 per hour, GET counts too
print("\n=== Rate Limiting Test (valid CSRF, same route) ===")
for i in range(7):
    if i == 0:
        resp = sess.get('http://127.0.0.1:5556/register/student')
        print(f"  Attempt {i+1} (GET):  Status={resp.status_code}, CT={resp.headers.get('Content-Type', '')}")
    else:
        # Get a fresh CSRF token from the session
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', resp.text)
        csrf = match.group(1) if match else 'dummy'
        
        form_data = {
            'csrf_token': csrf,
            'name': f'Rate Test {i}',
            'email': f'ratelimit{i}@test.com',
            'mobile': '+91 9999999999',
            'student_id': f'STU{i:04d}',
            'roll_no': f'ROLL{i:04d}',
            'course': 'B.Tech',
            'semester': '3',
            'academic_session': '2023-2024',
            'section': 'A',
            'department': 'CSE',
            'password': 'TestPass123!',
            'confirm_password': 'TestPass123!',
        }
        resp = sess.post('http://127.0.0.1:5556/register/student',
            data=form_data,
            headers={'X-Requested-With': 'XMLHttpRequest'})
        ct = resp.headers.get('Content-Type', '')
        print(f"  Attempt {i+1} (POST): Status={resp.status_code}, CT={ct}")
        if resp.status_code == 429:
            print(f"  >>> RATE LIMITED! Body: {resp.text[:200]}")
            print(f"  >>> Content-Type is HTML (not JSON)")
            print(f"  >>> In browser: response.json() would THROW -> catch() -> 'Network error'")
            break
        elif 'application/json' not in ct:
            print(f"  >>> NON-JSON response! Body: {resp.text[:200]}")
            break

# Test 2: Check if the /register route (main) also has rate limit
print("\n=== Testing /register (main) rate limit ===")
sess2 = requests.Session()
for i in range(7):
    resp = sess2.get('http://127.0.0.1:5556/register')
    print(f"  Attempt {i+1} (GET): Status={resp.status_code}, CT={resp.headers.get('Content-Type', '')}")
    if resp.status_code != 200:
        print(f"  Body: {resp.text[:200]}")
        break

# Test 3: Check the /api/register route
print("\n=== Testing /api/register rate limit ===")
sess3 = requests.Session()
for i in range(7):
    resp = sess3.get('http://127.0.0.1:5556/register/student')
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', resp.text)
    csrf = match.group(1) if match else 'dummy'
    resp = sess3.post('http://127.0.0.1:5556/api/register',
        data={'csrf_token': csrf,
              'name': f'API Test {i}',
              'email': f'apireg{i}@test.com',
              'mobile': '+91 9999999999',
              'student_id': f'API{i:04d}',
              'roll_no': f'APIROLL{i:04d}',
              'course': 'B.Tech',
              'semester': '3',
              'academic_session': '2023-2024',
              'section': 'A',
              'department': 'CSE',
              'password': 'TestPass123!',
              'confirm_password': 'TestPass123!'},
        headers={'X-Requested-With': 'XMLHttpRequest'})
    ct = resp.headers.get('Content-Type', '')
    print(f"  Attempt {i+1} (POST /api/register): Status={resp.status_code}, CT={ct}")
    if resp.status_code == 429:
        print(f"  >>> RATE LIMITED! Body: {resp.text[:200]}")
        break
    if 'application/json' in ct:
        data = resp.json()
        print(f"  >>> JSON: success={data.get('success')}, errors={data.get('errors')}")

print("\n=== Rate limit reset check ===")
try:
    limiter.reset()
    print("Rate limiter reset successfully")
except Exception as e:
    print(f"Reset failed: {e}")

print("\nDone!")
