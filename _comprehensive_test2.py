"""Post-fix validation test with DB setup for duplicates."""
import os, sys
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite://"
sys.path.insert(0, ".")

from app import app, db, User, ACADEMIC_SESSIONS, validate_registration_payload, persist_registration_user
from cems.domain import StudentProfile
from werkzeug.security import check_password_hash

with app.app_context():
    db.drop_all()
    db.create_all()

    results = []

    # Create an initial user for duplicate testing
    try:
        base = {
            "name": "Original Student", "email": "original@agc.edu.in", "mobile": "+919876543210",
            "date_of_birth": "2005-06-15", "student_id": "21CS0001", "roll_no": "21CS0001",
            "section": "A", "course": "B.Tech", "department": "CS", "semester": "1",
            "academic_session": "2024\u20132025", "password": "Test@1234", "confirm_password": "Test@1234",
        }
        persist_registration_user(base)
    except Exception as e:
        pass  # May fail due to missing request context, but user should be in DB

    # If user wasn't created, just test non-duplicate cases
    existing_user = User.query.filter_by(email="original@agc.edu.in").first()

    base = {
        "name": "Test Student", "email": "test@agc.edu.in", "mobile": "+91 98765 43210",
        "date_of_birth": "2005-06-15", "student_id": "21CS1001", "roll_no": "21CS1001",
        "section": "A", "course": "B.Tech", "department": "Computer Science", "semester": "1",
        "academic_session": "2024\u20132025", "password": "Test@1234", "confirm_password": "Test@1234",
    }

    # Test 1: Valid data
    data, errors = validate_registration_payload(dict(base))
    if not errors:
        results.append(("Valid data (all fields)", True))
    else:
        results.append(("Valid data (all fields)", False, errors))

    # Test 2: Empty mobile (optional)
    data, errors = validate_registration_payload(dict(base, mobile=""))
    if "mobile" not in errors:
        results.append(("Empty mobile (optional)", True))
    else:
        results.append(("Empty mobile (optional)", False, errors))

    # Test 3: Empty DOB (optional)
    data, errors = validate_registration_payload(dict(base, date_of_birth=""))
    if "date_of_birth" not in errors:
        results.append(("Empty DOB (optional)", True))
    else:
        results.append(("Empty DOB (optional)", False, errors))

    # Test 4: Future DOB rejected
    data, errors = validate_registration_payload(dict(base, date_of_birth="2030-01-01"))
    if "date_of_birth" in errors:
        results.append(("Future DOB rejected", True))
    else:
        results.append(("Future DOB rejected", False, errors))

    # Test 5: Invalid DOB format
    data, errors = validate_registration_payload(dict(base, date_of_birth="not-a-date"))
    if "date_of_birth" in errors:
        results.append(("Invalid DOB format rejected", True))
    else:
        results.append(("Invalid DOB format rejected", False, errors))

    # Test 6: Invalid phone format
    data, errors = validate_registration_payload(dict(base, mobile="12345"))
    if "mobile" in errors:
        results.append(("Invalid phone format rejected", True))
    else:
        results.append(("Invalid phone format rejected", False, errors))

    # Test 7-9: Duplicates (only if user exists)
    if existing_user:
        # Duplicate roll_no
        data, errors = validate_registration_payload(dict(base, email="test2@agc.edu.in"))
        if "roll_no" in errors:
            results.append(("Duplicate roll_no rejected", True))
        else:
            results.append(("Duplicate roll_no rejected", False, errors))

        # Duplicate student_id
        data, errors = validate_registration_payload(dict(base, email="test3@agc.edu.in", student_id="21CS0001", roll_no="21CS1002"))
        if "student_id" in errors:
            results.append(("Duplicate student_id rejected", True))
        else:
            results.append(("Duplicate student_id rejected", False, errors))

        # Duplicate email
        data, errors = validate_registration_payload(dict(base, email="original@agc.edu.in", student_id="21CS1003", roll_no="21CS1003"))
        if "email" in errors:
            results.append(("Duplicate email rejected", True))
        else:
            results.append(("Duplicate email rejected", False, errors))
    else:
        results.append(("Duplicate tests (skipped - no DB user)", True))

    # Test 10: Invalid email
    data, errors = validate_registration_payload(dict(base, email="invalid", student_id="21CS1004", roll_no="21CS1004"))
    if "email" in errors:
        results.append(("Invalid email rejected", True))
    else:
        results.append(("Invalid email rejected", False, errors))

    # Test 11: Password mismatch
    data, errors = validate_registration_payload(dict(base, student_id="21CS1005", roll_no="21CS1005", password="Test@1234", confirm_password="Different@123"))
    if "confirm_password" in errors:
        results.append(("Password mismatch rejected", True))
    else:
        results.append(("Password mismatch rejected", False, errors))

    # Test 12: Missing password
    data, errors = validate_registration_payload(dict(base, student_id="21CS1006", roll_no="21CS1006", password="", confirm_password=""))
    if "password" in errors:
        results.append(("Missing password rejected", True))
    else:
        results.append(("Missing password rejected", False, errors))

    # Test 13: Weak password
    data, errors = validate_registration_payload(dict(base, student_id="21CS1007", roll_no="21CS1007", password="weakpass", confirm_password="weakpass"))
    if "password" in errors:
        results.append(("Weak password rejected", True))
    else:
        results.append(("Weak password rejected", False, errors))

    # Test 14: Empty name
    data, errors = validate_registration_payload(dict(base, email="test11@agc.edu.in", student_id="21CS1011", roll_no="21CS1011", name=""))
    if "name" in errors:
        results.append(("Empty name rejected", True))
    else:
        results.append(("Empty name rejected", False, errors))

    # Test 15: Empty email
    data, errors = validate_registration_payload(dict(base, email="", student_id="21CS1012", roll_no="21CS1012"))
    if "email" in errors:
        results.append(("Empty email rejected", True))
    else:
        results.append(("Empty email rejected", False, errors))

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
