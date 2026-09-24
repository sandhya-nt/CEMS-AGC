"""Comprehensive reproduction of the registration 'Network Error' issue.

Simulates the EXACT browser behavior: GET page (get CSRF), then POST via
fetch() equivalent (FormData + X-Requested-With header, then response.json()).
Uses a fresh app/database to avoid rate limit contamination from prior runs.
"""
import os
import re
import sys
import json

# Force fresh test DB and disable rate limits to isolate the real cause
os.environ['DATABASE_URL'] = 'sqlite:///cems_test_repro.db'
os.environ['SECRET_KEY'] = 'dev-secret-change-me'
os.environ['RATE_LIMIT_STORAGE_URI'] = 'memory://'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from cems.extensions import limiter

# Disable rate limiter to isolate CSRF/backend causes
limiter.enabled = False

with app.app_context():
    db.drop_all()
    db.create_all()

client = app.test_client()

def extract_csrf(html):
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    return match.group(1) if match else None

def simulate_browser_registration(url, form_id, form_data, label):
    """Simulate exactly what the browser's fetch() does."""
    print(f"\n{'='*70}")
    print(f"Testing: {label} ({url})")
    print(f"{'='*70}")

    # Step 1: GET the page (browser loads the form)
    resp_get = client.get(url)
    print(f"  GET {url}: Status={resp_get.status_code}")

    csrf_token = extract_csrf(resp_get.get_data(as_text=True))
    if not csrf_token:
        print("  ERROR: CSRF token not found on page!")
        return

    print(f"  CSRF token: {csrf_token[:60]}...")

    # Check session cookie
    cookies = resp_get.headers.getlist('Set-Cookie')
    print(f"  Set-Cookie headers: {len(cookies)}")

    # Step 2: Simulate fetch(form.action, {method: 'POST', body: FormData, headers: {'X-Requested-With': 'XMLHttpRequest'}})
    post_data = dict(form_data)
    post_data['csrf_token'] = csrf_token

    resp_post = client.post(url,
        data=post_data,
        content_type='multipart/form-data',
        headers={'X-Requested-With': 'XMLHttpRequest'})

    print(f"  POST {url}: Status={resp_post.status_code}")
    print(f"  Content-Type: {resp_post.content_type}")

    body = resp_post.get_data(as_text=True)
    print(f"  Response body (first 300): {body[:300]}")

    # This is the critical line that the frontend JS does:
    # .then(function(response) { return response.json(); })
    is_json = resp_post.is_json
    print(f"  Is JSON? {is_json}")

    if not is_json:
        print(f"  >>> CRITICAL: response.json() would THROW in the browser!")
        print(f"  >>> The .catch() handler would display 'Network error. Please try again.'")
        # Try to parse as JSON to confirm the error
        try:
            json.loads(body)
        except json.JSONDecodeError as e:
            print(f"  >>> JSON parse error: {e}")
            print(f"  >>> This is the ROOT CAUSE of the 'Network Error' message")
    else:
        data = resp_post.get_json()
        print(f"  JSON data: {data}")
        if data and data.get('success'):
            print(f"  >>> SUCCESS: Account created (or validation passed)")
        else:
            print(f"  >>> Validation errors (NOT 'Network error'): {data.get('errors')}")

# Test 1: Student registration (fresh, no duplicates)
simulate_browser_registration(
    '/register/student',
    'student-register-form',
    {
        'name': 'Test Student',
        'email': 'newstudent@test.com',
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
    'Student Registration (valid data)'
)

# Test 2: Faculty registration
simulate_browser_registration(
    '/register/faculty',
    'faculty-register-form',
    {
        'name': 'Test Faculty',
        'email': 'newfaculty@test.com',
        'mobile': '+91 1234567891',
        'employee_id': 'FAC001',
        'role': 'faculty',
        'department': 'Computer Science',
        'designation': 'Assistant Professor',
        'faculty_role': 'Faculty Member',
        'password': 'TestPass123!',
        'confirm_password': 'TestPass123!',
    },
    'Faculty Registration (valid data)'
)

# Test 3: Organizer registration
simulate_browser_registration(
    '/register/organizer',
    'organizer-register-form',
    {
        'name': 'Test Organizer',
        'email': 'neworganizer@test.com',
        'mobile': '+91 1234567892',
        'employee_id': 'ORG001',
        'role': 'organizer',
        'department': 'Student Affairs',
        'organizer_name': 'Event Coordinator',
        'event_category': 'General',
        'password': 'TestPass123!',
        'confirm_password': 'TestPass123!',
    },
    'Organizer Registration (valid data)'
)

# Test 4: Now test WITH rate limiting enabled (fresh app instance)
print(f"\n{'='*70}")
print("Testing with RATE LIMITING enabled (5 per hour per route)")
print(f"{'='*70}")

# Re-enable rate limiter
limiter.enabled = True

# Create a fresh client with rate limiter
client2 = app.test_client()

# Get CSRF token and submit 6 times to trigger rate limit
resp_get = client2.get('/register/student')
csrf_token2 = extract_csrf(resp_get.get_data(as_text=True))
form_data2 = {
    'csrf_token': csrf_token2,
    'name': 'Rate Test',
    'email': 'ratetest@test.com',
    'mobile': '+91 1234567893',
    'student_id': 'STU002',
    'roll_no': 'ROLL002',
    'course': 'B.Tech',
    'semester': '3',
    'academic_session': '2023-2024',
    'section': 'A',
    'department': 'Computer Science',
    'password': 'TestPass123!',
    'confirm_password': 'TestPass123!',
}

for i in range(6):
    resp = client2.post('/register/student',
        data=form_data2,
        content_type='multipart/form-data',
        headers={'X-Requested-With': 'XMLHttpRequest'})
    print(f"  Attempt {i+1}: Status={resp.status_code}, Content-Type={resp.content_type}, is_json={resp.is_json}")
    if not resp.is_json:
        body = resp.get_data(as_text=True)
        print(f"  >>> NON-JSON response! Body: {body[:200]}")
        print(f"  >>> This causes response.json() to FAIL → 'Network error' in browser")
    else:
        print(f"  >>> JSON response: {resp.get_json()}")

print(f"\n{'='*70}")
print("SUMMARY")
print(f"{'='*70}")
print("Root cause: When any error response returns HTML (not JSON),")
print("  response.json() throws, .catch() shows 'Network error.'")
print("  This happens with:")
print("  1. CSRF failure (400 HTML)")
print("  2. Rate limit exceeded (429 HTML)")
print("  3. Any unhandled server error (500 HTML)")
print()
print("The fetch() then .json() chain in all 3 register templates")
print("  does NOT check response.ok or Content-Type before calling .json()")
