import os
os.environ['FLASK_DEBUG'] = '0'
os.environ['FLASK_ENV'] = 'development'

from app import app, db, User, StudentProfile, AccountStatus
from werkzeug.security import generate_password_hash

print("=== Setup ===")
with app.app_context():
    db.create_all()
    # Ensure student user exists
    student = User.query.filter_by(email="student@agc.local").first()
    if not student:
        student = User(
            name="Student User", email="student@agc.local", role="student",
            is_verified=True, account_status=AccountStatus.ACTIVE,
            department="Computer Science", roll_no="21CS1001",
            student_id="STU2024001", mobile="9876543210",
        )
        student.set_password("Student@123")
        db.session.add(student)
        db.session.flush()
        sp = StudentProfile.query.filter_by(user_id=student.id).first()
        if not sp:
            sp = StudentProfile(user_id=student.id, student_id="STU2024001",
                roll_no="21CS1001", course="B.Tech", semester="5",
                department="Computer Science")
            db.session.add(sp)
        db.session.commit()
        print(f"Created student user: {student.email}")
    else:
        print(f"Student user exists: {student.email}")

# Test with Flask test client
app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing

client = app.test_client()

print("\n=== Test 1: GET /login ===")
resp = client.get('/login')
print(f"Status: {resp.status_code}")

print("\n=== Test 2: POST /login (student) ===")
resp = client.post('/login', data={
    'email': 'student@agc.local',
    'password': 'Student@123',
}, follow_redirects=False)
print(f"Status: {resp.status_code}")
if resp.status_code == 500:
    print(f"ERROR: {resp.data.decode()[:1000]}")

print("\n=== Test 3: GET /student/dashboard (logged in) ===")
resp = client.get('/student/dashboard')
print(f"Status: {resp.status_code}")
if resp.status_code == 500:
    body = resp.data.decode()
    # Find the error
    import re
    err = re.search(r'(jinja2|Template|Error|Exception)[^\n]*', body, re.IGNORECASE)
    if err:
        print(f"Error: {err.group()[:200]}")
    print(f"Body: {body[:500]}")

print("\n=== Test 4: GET /profile (logged in) ===")
resp = client.get('/profile')
print(f"Status: {resp.status_code}")
if resp.status_code == 500:
    print(f"ERROR: {resp.data.decode()[:1000]}")

print("\n=== Test 5: POST /profile (update profile) ===")
resp = client.post('/profile', data={
    'name': 'Student User',
    'mobile': '9876543210',
    'department': 'Computer Science',
    'roll_no': '21CS1001',
    'course': 'B.Tech Computer Science',
    'semester': '5',
    'bio': 'Test bio',
    'date_of_birth': '2002-05-15',
    'gender': 'male',
    'section': 'A',
    'academic_session': '2024-2025',
    'batch': '2024',
}, follow_redirects=False)
print(f"Status: {resp.status_code}")
if resp.status_code == 500:
    print(f"ERROR: {resp.data.decode()[:1000]}")

print("\n=== Test 6: GET /register/student ===")
resp = client.get('/register/student')
print(f"Status: {resp.status_code}")
if resp.status_code == 500:
    print(f"ERROR: {resp.data.decode()[:1000]}")

print("\n=== Test 7: POST /register/student ===")
resp = client.post('/register/student', data={
    'role': 'student',
    'name': 'New Test Student',
    'email': 'newteststudent@agc.local',
    'mobile': '9876543210',
    'password': 'Test@1234',
    'confirm_password': 'Test@1234',
    'student_id': 'STU2024002',
    'roll_no': 'CSE2024002',
    'department': 'Computer Science',
    'course': 'B.Tech Computer Science',
    'semester': '5',
    'academic_session': '2024-2025',
    'batch': '2024',
    'section': 'A',
    'date_of_birth': '2002-05-15',
    'gender': 'male',
}, follow_redirects=False)
print(f"Status: {resp.status_code}")
if resp.status_code == 500:
    print(f"ERROR: {resp.data.decode()[:1000]}")

print("\n=== Test 8: GET /login/student ===")
resp = client.get('/login/student')
print(f"Status: {resp.status_code}")
if resp.status_code == 500:
    print(f"ERROR: {resp.data.decode()[:1000]}")

print("\n=== All tests done ===")
