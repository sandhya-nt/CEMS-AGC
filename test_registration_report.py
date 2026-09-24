import sys
import os

os.environ['DATABASE_URL'] = 'sqlite:///test_reg_report.db'
os.environ['SECRET_KEY'] = 'test-secret-key'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, seed_data
from app import User, Event, Registration, EventFaculty

app.config['WTF_CSRF_ENABLED'] = False

# Set up data and get IDs
with app.app_context():
    db.drop_all()
    db.create_all()
    seed_data()
    db.session.commit()

    teacher = User.query.filter_by(email='teacher@agc.local').first()
    student = User.query.filter_by(email='student@agc.local').first()
    events = Event.query.limit(3).all()

    teacher_id = teacher.id
    student_id = student.id

    if student and events:
        for i, event in enumerate(events):
            status = ['pending', 'approved', 'rejected', 'waitlisted'][i % 4]
            reg = Registration(
                ticket_code=f"AGC-TEST{i:06X}",
                user_id=student.id,
                event_id=event.id,
                status=status,
                payment_status="free",
                terms_accepted=True,
            )
            db.session.add(reg)
        db.session.commit()

    for event in events:
        ef = EventFaculty(event_id=event.id, faculty_id=teacher.id)
        db.session.add(ef)
    db.session.commit()

client = app.test_client()

# Establish authenticated session
resp = client.post('/login', data={'email': 'admin@agc.local', 'password': 'Admin@123'})
print(f"Admin login: {resp.status_code}")

# Switch to teacher user via session
with client.session_transaction() as sess:
    sess['_user_id'] = str(teacher_id)

print(f"Teacher session set: user_id={teacher_id}")

results = []

# Test 1: Reports Page
print("\n=== Test 1: Reports Page ===")
resp = client.get('/teacher/reports')
ok = resp.status_code == 200
results.append(("Reports page 200", ok))
print(f"Status: {resp.status_code} - {'OK' if ok else 'FAIL'}")
if ok:
    content = resp.get_data(as_text=True)
    checks = [
        ('Reports & Analytics title', 'Reports & Analytics' in content),
        ('Event selector', 'All Assigned Events' in content),
        ('Registration Report section', 'Registration Report' in content),
        ('Total Registrations card', 'Total Registrations' in content),
        ('Pending card', 'Pending' in content),
        ('Approved card', 'Approved' in content),
        ('Rejected card', 'Rejected' in content),
        ('Waitlisted card', 'Waitlisted' in content),
        ('Load Report button', 'Load Report' in content),
    ]
    for name, result in checks:
        results.append((name, result))
        ok = ok and result
        print(f"  {name}: {'OK' if result else 'FAIL'}")
else:
    print(f"FAIL - {resp.get_data(as_text=True)[:300]}")

# Test 2: API with event_id
print("\n=== Test 2: API with event_id=1 ===")
resp = client.get('/api/teacher/reports/registration?event_id=1')
ok = resp.status_code == 200
results.append(("API event_id=1 200", ok))
print(f"Status: {resp.status_code} - {'OK' if ok else 'FAIL'}")
if ok:
    data = resp.get_json()
    if data and data.get('success'):
        stats = data['stats']
        total = stats['all']
        sum_parts = stats['pending'] + stats['approved'] + stats['rejected'] + stats['waitlisted']
        ok = total == sum_parts
        results.append(("API stats add up", ok))
        print(f"  Stats: {stats} - Total={total}, Sum={sum_parts} - {'OK' if ok else 'FAIL'}")
        print(f"  Registrations: {len(data.get('registrations', []))}")
        print(f"  Empty message: {data.get('empty_message')}")
        if data.get('registrations'):
            reg = data['registrations'][0]
            required = ['id', 'student_name', 'roll_no', 'course', 'department', 'semester', 'event_name', 'registration_date', 'status']
            missing = [k for k in required if k not in reg]
            ok = len(missing) == 0
            results.append(("API data structure", ok))
            print(f"  Data structure: {'OK' if ok else 'FAIL - missing: ' + str(missing)}")
            print(f"  Sample: {reg}")
    else:
        print(f"  API error: {data}")

# Test 3: API without event_id (All Assigned Events)
print("\n=== Test 3: API without event_id ===")
resp = client.get('/api/teacher/reports/registration')
ok = resp.status_code == 200
results.append(("API no event_id 200", ok))
print(f"Status: {resp.status_code} - {'OK' if ok else 'FAIL'}")
if ok:
    data = resp.get_json()
    if data and data.get('success'):
        stats = data['stats']
        total = stats['all']
        sum_parts = stats['pending'] + stats['approved'] + stats['rejected'] + stats['waitlisted']
        ok = total == sum_parts
        results.append(("API stats add up", ok))
        print(f"  Stats: {stats} - Total={total}, Sum={sum_parts} - {'OK' if ok else 'FAIL'}")
        print(f"  Empty message: {data.get('empty_message')}")

# Test 4: Unauthorized event_id
print("\n=== Test 4: Unauthorized event_id ===")
resp = client.get('/api/teacher/reports/registration?event_id=9999')
ok = resp.status_code == 403
results.append(("Unauthorized event 403", ok))
print(f"Status: {resp.status_code} - {'OK' if ok else 'FAIL'}")

# Test 5: Non-faculty blocked
print("\n=== Test 5: Non-faculty blocked ===")
with client.session_transaction() as sess:
    sess['_user_id'] = str(student_id)
resp = client.get('/teacher/reports')
ok = resp.status_code == 403
results.append(("Student blocked 403", ok))
print(f"Status: {resp.status_code} - {'OK' if ok else 'FAIL'}")

# Test 6: Data consistency
print("\n=== Test 6: Data consistency ===")
with app.app_context():
    with client.session_transaction() as sess:
        sess['_user_id'] = str(teacher_id)
    resp = client.get('/api/teacher/reports/registration?event_id=1')
    data = resp.get_json()
    if data and data.get('success') and data.get('registrations'):
        from app import Registration as RegModel
        db_regs = RegModel.query.filter_by(event_id=1).all()
        api_ids = {r['id'] for r in data['registrations']}
        db_ids = {r.id for r in db_regs}
        ok = api_ids == db_ids
        results.append(("Registration IDs match DB", ok))
        print(f"  API count: {len(api_ids)}, DB count: {len(db_ids)} - {'OK' if ok else 'FAIL'}")
    else:
        print("  No registrations to compare")

# Test 7: No duplicate data
print("\n=== Test 7: No duplicate data ===")
with app.app_context():
    from app import Registration as RegModel
    all_regs = RegModel.query.all()
    unique_tickets = set(r.ticket_code for r in all_regs if r.ticket_code)
    ok = len(all_regs) == len(unique_tickets)
    results.append(("No duplicate registrations", ok))
    print(f"  Total: {len(all_regs)}, Unique: {len(unique_tickets)} - {'OK' if ok else 'FAIL'}")

# Summary
print("\n" + "="*60)
print("TEST SUMMARY")
print("="*60)
all_passed = True
for name, result in results:
    status = "PASS" if result else "FAIL"
    if not result:
        all_passed = False
    print(f"  [{status}] {name}")
print("="*60)
print(f"Overall: {'ALL PASSED' if all_passed else 'SOME FAILED'}")
