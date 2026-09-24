from app import app, db, Event, EventFaculty, User, Registration, Attendance


def login(client, email, password):
    rv = client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)
    return rv.status_code == 200


def logout(client):
    client.get('/logout')


def setup_test_data():
    with app.app_context():
        db.drop_all()
        db.create_all()

        admin = User(name="AGC Admin", email="admin@agc.local", role="admin", is_verified=True, department="Administration")
        admin.set_password("Admin@123")
        organizer = User(name="AGC Event Organizer", email="organizer@agc.local", role="organizer", is_verified=True, department="Student Affairs")
        organizer.set_password("Organizer@123")
        student_a = User(name="Student A", email="studentA@agc.local", role="student", is_verified=True, department="Computer Science", roll_no="21CS1001", mobile="9876543210")
        student_a.set_password("Student@123")
        student_b = User(name="Student B", email="studentB@agc.local", role="student", is_verified=True, department="Computer Science", roll_no="21CS1002", mobile="9876543211")
        student_b.set_password("Student@123")
        faculty_a = User(name="Prof. Amit A", email="facultyA@agc.local", role="teacher", is_verified=True, department="Computer Science", mobile="9876543212")
        faculty_a.set_password("Teacher@123")
        faculty_b = User(name="Prof. Amit B", email="facultyB@agc.local", role="teacher", is_verified=True, department="Computer Science", mobile="9876543213")
        faculty_b.set_password("Teacher@123")
        db.session.add_all([admin, organizer, student_a, student_b, faculty_a, faculty_b])
        db.session.flush()

        event_a = Event(title="Event A - Faculty A's Event", category="Academic", event_type="free", date=datetime(2026, 10, 15).date(),
                        start_time="10:00 AM", end_time="12:00 PM", venue="Main Auditorium", capacity=100, fee=0, status="approved", organizer_id=organizer.id)
        event_b = Event(title="Event B - Faculty B's Event", category="Technical", event_type="free", date=datetime(2026, 10, 20).date(),
                        start_time="2:00 PM", end_time="4:00 PM", venue="Seminar Hall", capacity=100, fee=0, status="approved", organizer_id=organizer.id)
        db.session.add_all([event_a, event_b])
        db.session.flush()

        db.session.add(EventFaculty(event_id=event_a.id, faculty_id=faculty_a.id))
        db.session.add(EventFaculty(event_id=event_b.id, faculty_id=faculty_b.id))

        reg_approved_a = Registration(ticket_code="AGC-APPR01", user_id=student_a.id, event_id=event_a.id, status="approved", payment_status="free", attended=False)
        reg_pending_a = Registration(ticket_code="AGC-PEND01", user_id=student_b.id, event_id=event_a.id, status="pending", payment_status="free", attended=False)
        reg_rejected_a = Registration(ticket_code="AGC-REJ01", user_id=student_a.id, event_id=event_b.id, status="rejected", payment_status="free", attended=False)
        reg_confirmed_b = Registration(ticket_code="AGC-CONF01", user_id=student_a.id, event_id=event_b.id, status="confirmed", payment_status="free", attended=False)
        db.session.add_all([reg_approved_a, reg_pending_a, reg_rejected_a, reg_confirmed_b])
        db.session.commit()

        return event_a, event_b, faculty_a, faculty_b, student_a, student_b, reg_approved_a, reg_pending_a, reg_rejected_a, reg_confirmed_b


from datetime import datetime

with app.app_context():
    setup_test_data()

    print("=" * 60)
    print("PART 2 TESTS: Faculty Attendance Authorization")
    print("=" * 60)

    client = app.test_client()
    errors = []

    # ========== TEST 1: Faculty A + Faculty A's assigned event → allowed ==========
    print("\n--- Test 1: Faculty A + Faculty A's assigned event → allowed ---")
    logout(client)
    login(client, "facultyA@agc.local", "Teacher@123")
    event_a = Event.query.filter_by(title="Event A - Faculty A's Event").first()
    rv = client.post('/api/teacher/attendance/student',
                     json={"event_id": event_a.id, "student_id": 1, "status": "present"})
    status_code = rv.status_code
    body = rv.get_json()
    if status_code == 200 and body.get("success"):
        print("PASS: Attendance created for Faculty A's own event")
    else:
        errors.append(f"Test 1 FAILED: status={status_code}, body={body}")
        print(f"FAIL: status={status_code}, body={body}")

    # ========== TEST 2: Faculty A + Faculty B's event → rejected ==========
    print("\n--- Test 2: Faculty A + Faculty B's event → rejected ---")
    event_b = Event.query.filter_by(title="Event B - Faculty B's Event").first()
    rv = client.post('/api/teacher/attendance/student',
                     json={"event_id": event_b.id, "student_id": 1, "status": "present"})
    status_code = rv.status_code
    body = rv.get_json()
    if status_code == 403:
        print("PASS: Faculty A rejected from Faculty B's event")
    else:
        errors.append(f"Test 2 FAILED: expected 403, got {status_code}")
        print(f"FAIL: expected 403, got {status_code}")

    # ========== TEST 3: Faculty A + approved student of assigned event → allowed ==========
    print("\n--- Test 3: Faculty A + approved student of assigned event → allowed ---")
    reg = Registration.query.filter_by(status="approved", event_id=event_a.id).first()
    if reg:
        rv = client.post('/api/teacher/attendance/student',
                         json={"event_id": event_a.id, "student_id": reg.user_id, "status": "present"})
        status_code = rv.status_code
        body = rv.get_json()
        if status_code == 200 and body.get("success"):
            print("PASS: Approved student attendance allowed")
        else:
            errors.append(f"Test 3 FAILED: status={status_code}, body={body}")
            print(f"FAIL: status={status_code}, body={body}")
    else:
        errors.append("Test 3 FAILED: No approved registration found")
        print("FAIL: No approved registration found")

    # ========== TEST 4: Faculty A + rejected student → rejected ==========
    print("\n--- Test 4: Faculty A + rejected student → rejected ---")
    reg_rejected = Registration.query.filter_by(status="rejected").first()
    if reg_rejected:
        rv = client.post('/api/teacher/attendance/student',
                         json={"event_id": event_a.id, "student_id": reg_rejected.user_id, "status": "present"})
        status_code = rv.status_code
        body = rv.get_json()
        if status_code == 403:
            print("PASS: Rejected student blocked")
        else:
            errors.append(f"Test 4 FAILED: expected 403, got {status_code}")
            print(f"FAIL: expected 403, got {status_code}")
    else:
        errors.append("Test 4 FAILED: No rejected registration found")
        print("FAIL: No rejected registration found")

    # ========== TEST 5: Faculty A + pending student → rejected ==========
    print("\n--- Test 5: Faculty A + pending student → rejected ---")
    reg_pending = Registration.query.filter_by(status="pending", event_id=event_a.id).first()
    if reg_pending:
        rv = client.post('/api/teacher/attendance/student',
                         json={"event_id": event_a.id, "student_id": reg_pending.user_id, "status": "present"})
        status_code = rv.status_code
        body = rv.get_json()
        if status_code == 403:
            print("PASS: Pending student blocked")
        else:
            errors.append(f"Test 5 FAILED: expected 403, got {status_code}")
            print(f"FAIL: expected 403, got {status_code}")
    else:
        errors.append("Test 5 FAILED: No pending registration found")
        print("FAIL: No pending registration found")

    # ========== TEST 6: Faculty A + unregistered student → rejected ==========
    print("\n--- Test 6: Faculty A + unregistered student → rejected ---")
    student_b = User.query.filter_by(email="studentB@agc.local").first()
    rv = client.post('/api/teacher/attendance/student',
                     json={"event_id": event_a.id, "student_id": student_b.id, "status": "present"})
    status_code = rv.status_code
    body = rv.get_json()
    if status_code == 403:
        print("PASS: Unregistered student blocked")
    else:
        errors.append(f"Test 6 FAILED: expected 403, got {status_code}")
        print(f"FAIL: expected 403, got {status_code}")

    # ========== TEST 7: Same student + same event + existing attendance → no duplicate ==========
    print("\n--- Test 7: Same student + same event + existing attendance → no duplicate ---")
    reg_approved = Registration.query.filter_by(status="approved", event_id=event_a.id).first()
    if reg_approved:
        before_count = Attendance.query.filter_by(event_id=event_a.id, student_id=reg_approved.user_id).count()
        rv = client.post('/api/teacher/attendance/student',
                         json={"event_id": event_a.id, "student_id": reg_approved.user_id, "status": "absent"})
        status_code = rv.status_code
        body = rv.get_json()
        after_count = Attendance.query.filter_by(event_id=event_a.id, student_id=reg_approved.user_id).count()
        if status_code == 200 and before_count == after_count == 1:
            print("PASS: No duplicate created, existing record updated")
        else:
            errors.append(f"Test 7 FAILED: before={before_count}, after={after_count}, status={status_code}")
            print(f"FAIL: before={before_count}, after={after_count}, status={status_code}")
    else:
        errors.append("Test 7 FAILED: No approved registration found")
        print("FAIL: No approved registration found")

    # ========== TEST 8: Unauthorized user (student) → rejected ==========
    print("\n--- Test 8: Unauthorized user (student) → rejected ---")
    logout(client)
    login(client, "studentA@agc.local", "Student@123")
    event_a = Event.query.filter_by(title="Event A - Faculty A's Event").first()
    rv = client.post('/api/teacher/attendance/student',
                     json={"event_id": event_a.id, "student_id": 1, "status": "present"})
    status_code = rv.status_code
    if status_code == 403:
        print("PASS: Student unauthorized access rejected")
    else:
        errors.append(f"Test 8 FAILED: expected 403, got {status_code}")
        print(f"FAIL: expected 403, got {status_code}")

    # ========== BONUS: Verify existing attendance endpoint still works ==========
    print("\n--- Bonus: Existing attendance endpoint still works ---")
    logout(client)
    login(client, "facultyA@agc.local", "Teacher@123")
    event_a = Event.query.filter_by(title="Event A - Faculty A's Event").first()
    rv = client.get(f'/api/teacher/attendance/{event_a.id}')
    status_code = rv.status_code
    body = rv.get_json()
    if status_code == 200 and body.get("success"):
        print("PASS: Existing attendance GET endpoint works")
    else:
        errors.append(f"Bonus FAILED: status={status_code}")
        print(f"FAIL: status={status_code}")

    # ========== BONUS: Verify mark attendance endpoint still works ==========
    print("\n--- Bonus: Existing mark attendance endpoint still works ---")
    reg = Registration.query.filter_by(status="approved", event_id=event_a.id).first()
    if reg:
        rv = client.post(f'/api/teacher/attendance/{event_a.id}/{reg.id}/mark',
                         json={"status": "present"})
        status_code = rv.status_code
        if status_code == 200:
            print("PASS: Existing mark endpoint works")
        else:
            errors.append(f"Bonus mark FAILED: status={status_code}")
            print(f"FAIL: status={status_code}")

    # ========== BONUS: Verify role_required still blocks non-teacher ==========
    print("\n--- Bonus: role_required still blocks non-faculty ---")
    logout(client)
    login(client, "studentA@agc.local", "Student@123")
    rv = client.get('/teacher/attendance')
    if rv.status_code == 403:
        print("PASS: Student blocked from attendance page")
    else:
        errors.append(f"Bonus page FAILED: expected 403, got {rv.status_code}")
        print(f"FAIL: expected 403, got {rv.status_code}")

    print("\n" + "=" * 60)
    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        for e in errors:
            print(f"  - {e}")
    else:
        print("ALL PART 2 TESTS PASSED")
    print("=" * 60)
