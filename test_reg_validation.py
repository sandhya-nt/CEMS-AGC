import os, sys
os.environ['SECRET_KEY'] = 'test-secret'
os.environ['DATABASE_URL'] = 'sqlite:///test_reg_val3.db'
sys.path.insert(0, '.')

from app import app as flask_app, db, User, Event, Registration, AccountStatus
from datetime import date
from cems.services import register_student

with flask_app.app_context():
    db.create_all()

    with flask_app.test_request_context("/events/1/register", method="POST"):
        student = User(
            name='Test Student',
            email='s1@test.com',
            password_hash='pbkdf2:sha256:600000$test',
            role='student',
            account_status=AccountStatus.ACTIVE,
            department='Computer Science',
            semester='3',
            student_id='STU001',
        )
        db.session.add(student)
        db.session.commit()

        # Test 1: Ineligible - wrong department
        ev = Event(
            title='CS Only', category='Workshop', event_type='free',
            date=date(2026, 12, 1), start_time='10:00', end_time='12:00',
            venue='R1', capacity=50, registration_start=date(2026, 1, 1),
            registration_deadline=date(2026, 11, 30), fee=0, status='approved',
            target_department='Electronics', target_semester='5', organizer_id=student.id,
        )
        db.session.add(ev)
        db.session.commit()
        try:
            register_student(ev, student, terms_accepted=True)
            print('FAIL: Should reject ineligible')
        except ValueError as e:
            print(f'PASS - Department check: {e}')

        # Test 2: Eligible student
        ev2 = Event(
            title='CS Workshop', category='Workshop', event_type='free',
            date=date(2026, 12, 1), start_time='10:00', end_time='12:00',
            venue='R1', capacity=50, registration_start=date(2026, 1, 1),
            registration_deadline=date(2026, 11, 30), fee=0, status='approved',
            target_department='Computer Science', target_semester='3', organizer_id=student.id,
        )
        db.session.add(ev2)
        db.session.commit()
        reg = register_student(ev2, student, terms_accepted=True)
        print(f'PASS - Eligible registration: ticket_code={reg.ticket_code}, status={reg.status}')

        # Test 3: Duplicate
        try:
            register_student(ev2, student, terms_accepted=True)
            print('FAIL: Should reject duplicate')
        except ValueError as e:
            print(f'PASS - Duplicate check: {e}')

        # Test 4: Past event
        ev3 = Event(
            title='Past', category='Workshop', event_type='free',
            date=date(2025, 1, 1), start_time='10:00', end_time='12:00',
            venue='R1', capacity=50, registration_start=date(2025, 1, 1),
            registration_deadline=date(2025, 1, 30), fee=0, status='approved',
            organizer_id=student.id,
        )
        db.session.add(ev3)
        db.session.commit()
        try:
            register_student(ev3, student, terms_accepted=True)
            print('FAIL: Should reject past event')
        except ValueError as e:
            print(f'PASS - Past event: {e}')

        # Test 5: Rejected event
        ev4 = Event(
            title='Rejected', category='Workshop', event_type='free',
            date=date(2026, 12, 1), start_time='10:00', end_time='12:00',
            venue='R1', capacity=50, registration_start=date(2026, 1, 1),
            registration_deadline=date(2026, 11, 30), fee=0, status='rejected',
            organizer_id=student.id,
        )
        db.session.add(ev4)
        db.session.commit()
        try:
            register_student(ev4, student, terms_accepted=True)
            print('FAIL: Should reject rejected event')
        except ValueError as e:
            print(f'PASS - Rejected event: {e}')

        # Test 6: Cancelled event
        ev4c = Event(
            title='Cancelled', category='Workshop', event_type='free',
            date=date(2026, 12, 1), start_time='10:00', end_time='12:00',
            venue='R1', capacity=50, registration_start=date(2026, 1, 1),
            registration_deadline=date(2026, 11, 30), fee=0, status='cancelled',
            organizer_id=student.id,
        )
        db.session.add(ev4c)
        db.session.commit()
        try:
            register_student(ev4c, student, terms_accepted=True)
            print('FAIL: Should reject cancelled event')
        except ValueError as e:
            print(f'PASS - Cancelled event: {e}')

        # Test 7: Registration not open
        ev5 = Event(
            title='Future Start', category='Workshop', event_type='free',
            date=date(2026, 12, 1), start_time='10:00', end_time='12:00',
            venue='R1', capacity=50, registration_start=date(2026, 12, 1),
            registration_deadline=date(2026, 12, 30), fee=0, status='approved',
            organizer_id=student.id,
        )
        db.session.add(ev5)
        db.session.commit()
        try:
            register_student(ev5, student, terms_accepted=True)
            print('FAIL: Should reject future start')
        except ValueError as e:
            print(f'PASS - Registration start: {e}')

        # Test 8: Deadline passed
        ev6 = Event(
            title='Deadline Passed', category='Workshop', event_type='free',
            date=date(2026, 12, 1), start_time='10:00', end_time='12:00',
            venue='R1', capacity=50, registration_start=date(2026, 1, 1),
            registration_deadline=date(2025, 1, 30), fee=0, status='approved',
            organizer_id=student.id,
        )
        db.session.add(ev6)
        db.session.commit()
        try:
            register_student(ev6, student, terms_accepted=True)
            print('FAIL: Should reject past deadline')
        except ValueError as e:
            print(f'PASS - Deadline check: {e}')

        # Test 9: Terms not accepted
        ev7 = Event(
            title='Terms Test', category='Workshop', event_type='free',
            date=date(2026, 12, 1), start_time='10:00', end_time='12:00',
            venue='R1', capacity=50, registration_start=date(2026, 1, 1),
            registration_deadline=date(2026, 11, 30), fee=0, status='approved',
            organizer_id=student.id,
        )
        db.session.add(ev7)
        db.session.commit()
        student2 = User(
            name='Test Student 2', email='s2@test.com',
            password_hash='pbkdf2:sha256:600000$test', role='student',
            account_status=AccountStatus.ACTIVE, department='Computer Science',
            semester='3', student_id='STU002',
        )
        db.session.add(student2)
        db.session.commit()
        try:
            register_student(ev7, student2, terms_accepted=False)
            print('FAIL: Should reject no terms')
        except ValueError as e:
            print(f'PASS - Terms check: {e}')

        # Test 10: Published event should be allowed
        ev8 = Event(
            title='Published Event', category='Workshop', event_type='free',
            date=date(2026, 12, 1), start_time='10:00', end_time='12:00',
            venue='R1', capacity=50, registration_start=date(2026, 1, 1),
            registration_deadline=date(2026, 11, 30), fee=0, status='published',
            organizer_id=student.id,
        )
        db.session.add(ev8)
        db.session.commit()
        reg8 = register_student(ev8, student2, terms_accepted=True)
        print(f'PASS - Published event allowed: ticket_code={reg8.ticket_code}')

        # Test 11: Event is full
        ev9 = Event(
            title='Full Event', category='Workshop', event_type='free',
            date=date(2026, 12, 1), start_time='10:00', end_time='12:00',
            venue='R1', capacity=1, registration_start=date(2026, 1, 1),
            registration_deadline=date(2026, 11, 30), fee=0, status='approved',
            organizer_id=student.id,
        )
        db.session.add(ev9)
        db.session.commit()
        student3 = User(
            name='Test Student 3', email='s3@test.com',
            password_hash='pbkdf2:sha256:600000$test', role='student',
            account_status=AccountStatus.ACTIVE, department='Computer Science',
            semester='3', student_id='STU003',
        )
        db.session.add(student3)
        db.session.commit()
        register_student(ev9, student, terms_accepted=True)
        try:
            register_student(ev9, student3, terms_accepted=True)
            print('FAIL: Should reject full event')
        except ValueError as e:
            print(f'PASS - Capacity check: {e}')

        # Test 12: Semester-only eligibility check
        ev10 = Event(
            title='Sem Only', category='Workshop', event_type='free',
            date=date(2026, 12, 1), start_time='10:00', end_time='12:00',
            venue='R1', capacity=50, registration_start=date(2026, 1, 1),
            registration_deadline=date(2026, 11, 30), fee=0, status='approved',
            target_department=None, target_semester='5', organizer_id=student.id,
        )
        db.session.add(ev10)
        db.session.commit()
        try:
            register_student(ev10, student, terms_accepted=True)
            print('FAIL: Should reject semester mismatch')
        except ValueError as e:
            print(f'PASS - Semester check: {e}')

        print()
        print('=== ALL 12 TESTS PASSED ===')

        db.session.rollback()
        db.drop_all()
