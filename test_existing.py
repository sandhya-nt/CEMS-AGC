import sys
import os

os.environ['DATABASE_URL'] = 'sqlite:///test_reg_report.db'
os.environ['SECRET_KEY'] = 'test-secret-key'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, seed_data
from app import User, Event, Registration, EventFaculty

app.config['WTF_CSRF_ENABLED'] = False

with app.app_context():
    db.drop_all()
    db.create_all()
    seed_data()
    db.session.commit()

    teacher = User.query.filter_by(email='teacher@agc.local').first()
    student = User.query.filter_by(email='student@agc.local').first()
    teacher_id = teacher.id
    student_id = student.id

client = app.test_client()

results = []

# Setup teacher session
resp = client.post('/login', data={'email': 'admin@agc.local', 'password': 'Admin@123'})
with client.session_transaction() as sess:
    sess['_user_id'] = str(teacher_id)

print("=== Test: Teacher Dashboard still works ===")
resp = client.get('/teacher/dashboard')
ok = resp.status_code == 200
results.append(("Teacher Dashboard", ok))
print(f"  Status: {resp.status_code} - {'OK' if ok else 'FAIL'}")

print("\n=== Test: Teacher Assigned Events ===")
resp = client.get('/faculty/assigned-events')
ok = resp.status_code == 200
results.append(("Assigned Events", ok))
print(f"  Status: {resp.status_code} - {'OK' if ok else 'FAIL'}")

print("\n=== Test: Teacher Registrations Manage ===")
resp = client.get('/teacher/registrations/manage')
ok = resp.status_code == 200
results.append(("Manage Registrations", ok))
print(f"  Status: {resp.status_code} - {'OK' if ok else 'FAIL'}")

print("\n=== Test: Teacher Attendance ===")
resp = client.get('/teacher/attendance')
ok = resp.status_code == 200
results.append(("Attendance", ok))
print(f"  Status: {resp.status_code} - {'OK' if ok else 'FAIL'}")

print("\n=== Test: Teacher Certificates ===")
resp = client.get('/teacher/certificates')
ok = resp.status_code == 200
results.append(("Certificates", ok))
print(f"  Status: {resp.status_code} - {'OK' if ok else 'FAIL'}")

print("\n=== Test: Existing API still works ===")
resp = client.get('/api/teacher/registrations')
ok = resp.status_code == 200
results.append(("Existing API /api/teacher/registrations", ok))
print(f"  Status: {resp.status_code} - {'OK' if ok else 'FAIL'}")
if ok:
    data = resp.get_json()
    if data:
        print(f"  Has stats: {'stats' in data}")
        print(f"  Has registrations: {'registrations' in data}")

print("\n=== Test: New Reports API ===")
resp = client.get('/api/teacher/reports/registration')
ok = resp.status_code == 200
results.append(("New API /api/teacher/reports/registration", ok))
print(f"  Status: {resp.status_code} - {'OK' if ok else 'FAIL'}")
if ok:
    data = resp.get_json()
    if data:
        print(f"  Has stats: {'stats' in data}")
        print(f"  Has registrations: {'registrations' in data}")

print("\n=== Test: New Reports Page ===")
resp = client.get('/teacher/reports')
ok = resp.status_code == 200
results.append(("Reports Page", ok))
print(f"  Status: {resp.status_code} - {'OK' if ok else 'FAIL'}")

# Test non-faculty still blocked
with client.session_transaction() as sess:
    sess['_user_id'] = str(student_id)
resp = client.get('/teacher/dashboard')
ok = resp.status_code == 403
results.append(("Student blocked from Dashboard", ok))
print(f"\n  Student blocked from Dashboard: {resp.status_code} - {'OK' if ok else 'FAIL'}")

# Test organizer still works
with client.session_transaction() as sess:
    sess['_user_id'] = str(student_id)  # reset
    # Actually test with organizer
    organizer = User.query.filter_by(email='organizer@agc.local').first()
    sess['_user_id'] = str(organizer.id)
resp = client.get('/organizer/reports')
ok = resp.status_code == 200
results.append(("Organizer Reports", ok))
print(f"  Organizer Reports: {resp.status_code} - {'OK' if ok else 'FAIL'}")

# Summary
print("\n" + "="*60)
print("EXISTING FUNCTIONALITY TEST SUMMARY")
print("="*60)
all_passed = True
for name, result in results:
    status = "PASS" if result else "FAIL"
    if not result:
        all_passed = False
    print(f"  [{status}] {name}")
print("="*60)
print(f"Overall: {'ALL PASSED' if all_passed else 'SOME FAILED'}")
