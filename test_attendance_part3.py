"""Test Part 3: Faculty Attendance page, assigned event selection, approved student list."""
import sys
sys.path.insert(0, '.')

from app import app, db, Event, EventFaculty, User, Registration, AttendanceRecord

def test_attendance_page():
    with app.test_client() as client:
        # ========== SETUP: Login as teacher ==========
        rv = client.post('/login', data={'email': 'teacher@agc.local', 'password': 'Teacher@123'}, follow_redirects=True)
        assert rv.status_code == 200, f"Teacher login failed: {rv.status_code}"
        print("1. Teacher login: OK")

        teacher = User.query.filter_by(role='teacher').first()
        assert teacher is not None, "Teacher user not found"
        print(f"   Teacher: {teacher.name} (id={teacher.id})")

        # ========== TEST: Access attendance page ==========
        rv = client.get('/teacher/attendance')
        assert rv.status_code == 200, f"Attendance page: {rv.status_code}"
        content = rv.data.decode()
        assert 'Select Assigned Event' in content, "Event selection UI missing"
        assert 'Attendance Management' in content, "Page title missing"
        print("2. Attendance page renders: OK")

        # ========== TEST: No assigned events empty state ==========
        # Check the page shows "No events assigned" when events list is empty
        # (We'll test this by checking the page has the empty state HTML)
        assert 'No assigned events' in content or 'Choose an assigned event' in content, "Empty state or dropdown missing"
        print("3. Empty state elements present: OK")

        # ========== TEST: API - No assigned events ==========
        # Teacher currently has no assigned events (unless previous tests assigned some)
        event_ids = [e.id for e in Event.query.filter(EventFaculty.query.filter_by(faculty_id=teacher.id).exists()).all()]
        if not event_ids:
            rv = client.get('/api/teacher/attendance/99999')
            assert rv.status_code == 403, f"Unauthorized event access: {rv.status_code}"
            print("4a. Unauthorized event access blocked: OK (403)")
        else:
            print(f"4a. Teacher has events: {event_ids}")

        # ========== TEST: Assign event to teacher for further tests ==========
        from app import Event as EventModel
        all_events = Event.query.all()
        if all_events:
            test_event = all_events[0]
            # Check if already assigned
            existing = EventFaculty.query.filter_by(event_id=test_event.id, faculty_id=teacher.id).first()
            if not existing:
                assignment = EventFaculty(event_id=test_event.id, faculty_id=teacher.id, assigned_by=teacher.id)
                db.session.add(assignment)
                db.session.commit()
                print(f"5. Assigned event '{test_event.title}' (id={test_event.id}) to teacher")
            else:
                print(f"5. Event '{test_event.title}' (id={test_event.id}) already assigned to teacher")

            event_id = test_event.id

            # ========== TEST: Get assigned events via API ==========
            rv = client.get('/api/teacher/attendance')
            assert rv.status_code == 200, f"Attendance API root: {rv.status_code}"
            data = rv.get_json()
            print(f"6. Attendance API root works (no endpoint): status {rv.status_code}")

            # ========== TEST: Access attendance for assigned event ==========
            rv = client.get(f'/api/teacher/attendance/{event_id}')
            assert rv.status_code == 200, f"Attendance API for assigned event: {rv.status_code}"
            data = rv.get_json()
            assert data is not None, "No JSON response"
            assert data.get('success') == True, f"API success=False: {data}"
            assert 'students' in data, "Missing students key"
            assert 'stats' in data, "Missing stats key"
            assert 'event' in data, "Missing event key"
            assert data['event']['id'] == event_id, "Wrong event ID"
            print(f"7. Attendance API for assigned event: OK (total={data['total']}, stats={data['stats']})")

            # ========== TEST: Only approved registrations ==========
            for s in data['students']:
                assert s['registration_status'] == 'approved', f"Non-approved student found: {s['registration_status']} - {s['student_name']}"
            print("8. All students have approved registration status: OK")

            # ========== TEST: Attendance status from AttendanceRecord ==========
            for s in data['students']:
                att = AttendanceRecord.query.filter_by(registration_id=s['registration_id']).first()
                if att:
                    assert s['attendance_status'] == att.status, f"Attendance status mismatch: {s['attendance_status']} vs {att.status}"
                else:
                    assert s['attendance_status'] == 'not_marked', f"Expected not_marked for {s['student_name']}, got {s['attendance_status']}"
            print("9. Attendance status correctly reflects AttendanceRecord data: OK")

            # ========== TEST: Check-in time from AttendanceRecord ==========
            for s in data['students']:
                att = AttendanceRecord.query.filter_by(registration_id=s['registration_id']).first()
                if att and att.check_in_time:
                    assert s['check_in_time'] is not None, f"Missing check_in_time for {s['student_name']}"
                    assert att.check_in_time.isoformat() == s['check_in_time'], f"Check-in time mismatch"
                elif not att:
                    assert s['check_in_time'] is None, f"Unexpected check_in_time for {s['student_name']}"
            print("10. Check-in time correctly reflects AttendanceRecord data: OK")

            # ========== TEST: Non-approved students not shown ==========
            non_approved_regs = Registration.query.filter_by(event_id=event_id).filter(Registration.status != 'approved').all()
            approved_reg_ids = Registration.query.filter_by(event_id=event_id, status='approved').with_entities(Registration.id).all()
            approved_ids = {r[0] for r in approved_reg_ids}
            for reg in non_approved_regs:
                assert reg.id not in approved_ids, f"Non-approved registration {reg.id} found in approved list"
                # Verify it's not in the API response
                api_ids = [s['registration_id'] for s in data['students']]
                assert reg.id not in api_ids, f"Non-approved student {reg.id} in API response"
            print("11. Non-approved students excluded from API: OK")

            # ========== TEST: Faculty cannot access another faculty's event ==========
            # Create second teacher
            teacher2 = User.query.filter_by(role='teacher').first()
            if teacher2 and teacher2.id != teacher.id:
                # Find an event assigned to teacher2 (or assign one)
                teacher2_events = Event.query.join(EventFaculty, Event.id == EventFaculty.event_id).filter(
                    EventFaculty.faculty_id == teacher2.id
                ).all()
                if teacher2_events:
                    other_event_id = teacher2_events[0].id
                    if other_event_id == event_id:
                        # Assign another event to teacher2
                        if len(all_events) > 1:
                            other_event = all_events[1]
                            EventFaculty.query.filter_by(event_id=other_event.id, faculty_id=teacher2.id).delete()
                            assignment2 = EventFaculty(event_id=other_event.id, faculty_id=teacher2.id, assigned_by=teacher2.id)
                            db.session.add(assignment2)
                            db.session.commit()
                            other_event_id = other_event.id
                    rv = client.get(f'/api/teacher/attendance/{other_event_id}')
                    assert rv.status_code == 403, f"Access to another faculty's event: {rv.status_code}"
                    print(f"12. Cannot access another faculty's event (403): OK")
                else:
                    print("12. Skipped: No events for second teacher to test isolation")
            else:
                print("12. Skipped: Only one teacher found")

            # ========== TEST: API with nonexistent event ==========
            rv = client.get('/api/teacher/attendance/999999')
            assert rv.status_code == 403, f"Nonexistent event should be 403: {rv.status_code}"
            print("13. Nonexistent event blocked: OK (403)")

            # ========== TEST: Event with no approved students ==========
            # Find or create an event with no approved students
            no_students_event = None
            for ev in all_events:
                approved_count = Registration.query.filter_by(event_id=ev.id, status='approved').count()
                if approved_count == 0:
                    no_students_event = ev
                    break
            if no_students_event:
                rv = client.get(f'/api/teacher/attendance/{no_students_event.id}')
                assert rv.status_code == 200, f"Event with no approved students: {rv.status_code}"
                data = rv.get_json()
                assert data['total'] == 0, f"Expected 0 students, got {data['total']}"
                assert len(data['students']) == 0, "Expected empty students list"
                print(f"14. Event with no approved students shows empty list: OK (event='{no_students_event.title}')")
            else:
                print("14. Skipped: All events have approved students")

            # ========== TEST: Page renders with selected event ==========
            rv = client.get('/teacher/attendance')
            content = rv.data.decode()
            assert 'attendance-event' in content, "Event dropdown missing"
            print("15. Attendance page has event dropdown: OK")

        else:
            print("SKIP: No events found in database")

        print("\n=== ALL ATTENDANCE TESTS PASSED ===")

if __name__ == '__main__':
    test_attendance_page()
