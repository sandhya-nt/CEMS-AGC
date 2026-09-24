"""Test duplicate detection with proper DB setup."""
import os, sys
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite://"
sys.path.insert(0, ".")

from app import app, db, User, ACADEMIC_SESSIONS, validate_registration_payload, persist_registration_user
from cems.domain import StudentProfile

with app.app_context():
    db.drop_all()
    db.create_all()

    results = []

    # Create first user via persist_registration_user (needs request context)
    with app.test_request_context():
        user_data = {
            "name": "Original User", "email": "original@agc.edu.in",
            "mobile": "+919876543210", "date_of_birth": "2005-06-15",
            "student_id": "21CS0001", "roll_no": "21CS0001",
            "section": "A", "course": "B.Tech", "department": "CS",
            "semester": "1", "academic_session": "2024\u20132025",
            "password": "Test@1234", "confirm_password": "Test@1234", "role": "student",
        }
        try:
            persist_registration_user(user_data)
            results.append(("User creation", True))
        except Exception as e:
            results.append(("User creation", False, str(e)))

    # Check user exists
    user = User.query.filter_by(email="original@agc.edu.in").first()
    if user:
        results.append(("User in DB", True))
    else:
        results.append(("User in DB", False))

    base = {
        "name": "Test", "email": "test@agc.edu.in", "mobile": "+919876543210",
        "date_of_birth": "2005-06-15", "student_id": "21CS1001", "roll_no": "21CS1001",
        "section": "A", "course": "B.Tech", "department": "CS", "semester": "1",
        "academic_session": "2024\u20132025", "password": "Test@1234", "confirm_password": "Test@1234",
    }

    # Test 1: Duplicate email
    data, errors = validate_registration_payload(dict(base, email="original@agc.edu.in", student_id="21CS1002", roll_no="21CS1002"))
    if "email" in errors:
        results.append(("Duplicate email detection", True))
    else:
        results.append(("Duplicate email detection", False, errors))

    # Test 2: Duplicate student_id
    data, errors = validate_registration_payload(dict(base, email="other@agc.edu.in", student_id="21CS0001", roll_no="21CS1002"))
    if "student_id" in errors:
        results.append(("Duplicate student_id detection", True))
    else:
        results.append(("Duplicate student_id detection", False, errors))

    # Test 3: Duplicate roll_no
    data, errors = validate_registration_payload(dict(base, email="other@agc.edu.in", student_id="21CS1002", roll_no="21CS0001"))
    if "roll_no" in errors:
        results.append(("Duplicate roll_no detection", True))
    else:
        results.append(("Duplicate roll_no detection", False, errors))

    print("\n=== ALL RESULTS ===")
    all_pass = True
    for r in results:
        if r[1]:
            print(f"PASS {r[0]}")
        else:
            all_pass = False
            print(f"FAIL {r[0]}: {r[2] if len(r) > 2 else 'Unknown'}")

    if all_pass:
        print("\n=== ALL TESTS PASSED ===")
    else:
        print("\n=== SOME TESTS FAILED ===")
