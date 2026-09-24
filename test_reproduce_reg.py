"""Reproduce the registration 'Network Error' issue."""
import os
import sys

# Use the project's database
os.environ['DATABASE_URL'] = 'sqlite:///cems.db'
os.environ['SECRET_KEY'] = 'dev-secret-change-me'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from flask_wtf.csrf import CSRFError

# We'll test WITH CSRF enabled (as in production)
client = app.test_client()

print(f"CSRF ENABLED: {app.config.get('WTF_CSRF_ENABLED', True)}")
print(f"SECRET_KEY: {app.config.get('SECRET_KEY', 'NOT SET')[:30]}...")
print(f"DATABASE_URL: {app.config.get('SQLALCHEMY_DATABASE_URI', 'NOT SET')}")
print(f"MAX_CONTENT_LENGTH: {app.config.get('MAX_CONTENT_LENGTH')}")
print()

# Step 1: GET the student registration page to get CSRF token
print("=== Step 1: GET /register/student ===")
resp = client.get('/register/student')
print(f"Status: {resp.status_code}")

# Extract CSRF token from the response
csrf_token = None
if resp.status_code == 200:
    html = resp.get_data(as_text=True)
    # Find the csrf_token value
    import re
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if match:
        csrf_token = match.group(1)
        print(f"CSRF token found: {csrf_token[:50]}...")
    else:
        print("ERROR: CSRF token NOT found in page!")
else:
    print(f"Page returned {resp.status_code}, cannot get CSRF token")

# Check session cookie
print(f"Session cookie in response: {'Set-Cookie' in resp.headers}")
if 'Set-Cookie' in resp.headers:
    cookie = resp.headers.get('Set-Cookie', '')
    print(f"Cookie: {cookie[:100]}")

print()

if csrf_token:
    # Step 2: Simulate the fetch() call - POST with FormData + X-Requested-With header
    # FormData multipart/form-data with CSRF token + form fields
    print("=== Step 2: POST /register/student (simulating fetch with FormData) ===")
    
    data = {
        'csrf_token': csrf_token,
        'name': 'Test Student',
        'email': 'teststudent@test.com',
        'mobile': '+91 1234567890',
        'student_id': '21CS1001',
        'roll_no': '21CS1001',
        'course': 'B.Tech',
        'semester': '3',
        'academic_session': '2023-2024',
        'section': 'A',
        'department': 'Computer Science',
        'password': 'TestPass123!',
        'confirm_password': 'TestPass123!',
    }
    
    resp2 = client.post('/register/student', 
        data=data,
        content_type='multipart/form-data',
        headers={'X-Requested-With': 'XMLHttpRequest'})
    
    print(f"Status: {resp2.status_code}")
    print(f"Content-Type: {resp2.content_type}")
    body = resp2.get_data(as_text=True)
    print(f"Response body (first 500 chars): {body[:500]}")
    
    # Check if response is JSON
    if resp2.is_json:
        print(f"JSON response: {resp2.get_json()}")
    else:
        print("RESPONSE IS NOT JSON!")
        print("This would cause response.json() to fail in the frontend!")
        print("The .catch() block would show 'Network error. Please try again.'")
    
    print()

    # Step 3: Also try without CSRF to see if that's the issue
    print("=== Step 3: POST without CSRF token (to confirm CSRF is the issue) ===")
    data_no_csrf = dict(data)
    del data_no_csrf['csrf_token']
    
    resp3 = client.post('/register/student',
        data=data_no_csrf,
        content_type='multipart/form-data',
        headers={'X-Requested-With': 'XMLHttpRequest'})
    
    print(f"Status: {resp3.status_code}")
    print(f"Content-Type: {resp3.content_type}")
    body3 = resp3.get_data(as_text=True)
    print(f"Response body (first 500 chars): {body3[:500]}")
    
    if resp3.is_json:
        print(f"JSON response: {resp3.get_json()}")
    else:
        print("RESPONSE IS NOT JSON!")
        print(f"Status code {resp3.status_code} - this is what causes 'Network Error'")
    
    print()
    
    # Step 4: Try with rate limit exceeded (make 6 requests)
    print("=== Step 4: Testing rate limiting (5 per hour) ===")
    for i in range(6):
        resp_rl = client.post('/register/student',
            data=data,
            content_type='multipart/form-data',
            headers={'X-Requested-With': 'XMLHttpRequest'})
        print(f"  Attempt {i+1}: Status={resp_rl.status_code}, Content-Type={resp_rl.content_type}, is_json={resp_rl.is_json}")
        if resp_rl.status_code != 200:
            body_rl = resp_rl.get_data(as_text=True)
            print(f"  Body (first 200): {body_rl[:200]}")

else:
    print("\nCannot proceed - no CSRF token. Trying without CSRF...")
    # This might reveal if CSRF is the root cause
