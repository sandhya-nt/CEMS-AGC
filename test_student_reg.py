"""Test student registration flow end-to-end."""
import os
import sys

os.environ["SECRET_KEY"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///test_student_reg.db"

sys.path.insert(0, ".")

from app import app, db, User, ACADEMIC_SESSIONS
from cems.domain import StudentProfile

# Clean up any old test db
if os.path.exists("instance/test_student_reg.db"):
    os.remove("instance/test_student_reg.db")

with app.app_context():
    db.create_all()

    # Test 1: ACADEMIC_SESSIONS has all required values
    assert "2021–2022" in ACADEMIC_SESSIONS, "Missing 2021-2022"
    assert "2022–2023" in ACADEMIC_SESSIONS, "Missing 2022-2023"
    assert "2023–2024" in ACADEMIC_SESSIONS, "Missing 2023-2024"
    assert "2024–2025" in ACADEMIC_SESSIONS, "Missing 2024-2025"
    assert "2025–2026" in ACADEMIC_SESSIONS, "Missing 2025-2026"
    assert "2026–2027" in ACADEMIC_SESSIONS, "Missing 2026-2027"
    print("✓ ACADEMIC_SESSIONS has all 6 required sessions")

    # Test 2: validate_registration_payload with valid student data
    from app import validate_registration_payload

    form_data = {
        "name": "Test Student",
        "email": "test@agc.edu.in",
        "mobile": "+91 98765 43210",
        "date_of_birth": "2005-06-15",
        "student_id": "21CS1001",
        "roll_no": "21CS1001",
        "section": "A",
        "course": "B.Tech",
        "department": "Computer Science",
        "semester": "1",
        "academic_session": "2024–2025",
        "batch": "2024",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
    }

    data, errors = validate_registration_payload(form_data)
    assert not errors, f"Validation errors: {errors}"
    assert data["roll_no"] == "21CS1001", f"roll_no not extracted: {data.get('roll_no')}"
    assert data["section"] == "A", f"section not extracted: {data.get('section')}"
    assert data["date_of_birth"] is not None, f"date_of_birth not extracted: {data.get('date_of_birth')}"
    assert data["academic_session"] == "2024–2025", f"academic_session not extracted: {data.get('academic_session')}"
    assert data["batch"] == "2024", f"batch not extracted: {data.get('batch')}"
    print("✓ validate_registration_payload extracts all student fields correctly")

    # Test 3: validate rejects duplicate roll_no
    form_data_dup = dict(form_data, email="test2@agc.edu.in")
    data2, errors2 = validate_registration_payload(form_data_dup)
    assert "roll_no" in errors2, f"Expected roll_no error for duplicate, got: {errors2}"
    print("✓ Duplicate roll_no is rejected")

    # Test 4: validate rejects invalid email
    form_data_bad = dict(form_data, email="invalid-email", student_id="21CS1002", roll_no="21CS1002")
    data3, errors3 = validate_registration_payload(form_data_bad)
    assert "email" in errors3, f"Expected email error, got: {errors3}"
    print("✓ Invalid email is rejected")

    # Test 5: validate rejects mismatched passwords
    form_data_pw = dict(form_data, student_id="21CS1002", roll_no="21CS1002", password="Test@1234", confirm_password="Different@123")
    data4, errors4 = validate_registration_payload(form_data_pw)
    assert "confirm_password" in errors4, f"Expected confirm_password error, got: {errors4}"
    print("✓ Mismatched passwords are rejected")

    # Test 6: validate rejects missing required fields
    form_data_min = dict(form_data, email="test3@agc.edu.in", student_id="21CS1003", roll_no="21CS1003", batch="")
    data5, errors5 = validate_registration_payload(form_data_min)
    assert "name" in errors5, f"Expected name error, got: {errors5}"
    assert "batch" in errors5, f"Expected batch error, got: {errors5}"
    assert "password" in errors5, f"Expected password error, got: {errors5}"
    print("✓ Missing required fields are rejected")

    # Test 7: persist_registration_user creates user and profile
    from app import persist_registration_user
    from flask import request

    # Mock request with files
    class FakeFile:
        filename = None

    class FakeRequest:
        files = {"profile_photo": None}

    # We can't easily test persist_registration_user without a full request context,
    # but let's verify the function exists and has the right signature
    import inspect
    sig = inspect.signature(persist_registration_user)
    print(f"✓ persist_registration_user signature: {sig}")

    # Test 8: Verify persisted student profile includes the separate batch
    with app.test_request_context("/register/student", method="POST", data={}):
        created_user = persist_registration_user(dict(
            form_data,
            email="persisted@agc.edu.in",
            student_id="21CS2001",
            roll_no="21CS2001",
        ))
    saved_profile = StudentProfile.query.filter_by(user_id=created_user.id).first()
    assert saved_profile is not None, "StudentProfile was not created"
    assert saved_profile.batch == "2024", f"batch not persisted: {saved_profile.batch}"
    print("✓ StudentProfile persists the separate Batch field")

    # Test 9: Verify StudentProfile model has all required fields
    profile_fields = [c.name for c in StudentProfile.__table__.columns]
    required_fields = ["user_id", "student_id", "roll_no", "course", "semester", "section", "academic_session", "batch", "department", "date_of_birth"]
    for field in required_fields:
        assert field in profile_fields, f"StudentProfile missing field: {field}"
    print(f"✓ StudentProfile has all required fields: {required_fields}")

    # Test 10: Verify User model has roll_no and student_id
    user_fields = [c.name for c in User.__table__.columns]
    assert "roll_no" in user_fields, "User missing roll_no"
    assert "student_id" in user_fields, "User missing student_id"
    assert "course" in user_fields, "User missing course"
    assert "semester" in user_fields, "User missing semester"
    print(f"✓ User model has all required fields")

    print("\n=== ALL TESTS PASSED ===")
