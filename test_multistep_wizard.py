"""Comprehensive test for multi-step registration wizard."""
import json
import os
import sys

# Set environment variables BEFORE importing app
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CELERY_ALWAYS_EAGER"] = "True"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app


def setup_app():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        from cems.extensions import db
        db.drop_all()
        db.create_all()

    return app.test_client()


def test_student_registration_page_loads(client):
    """Test that student registration page loads with stepper."""
    response = client.get("/register/student")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "student-register-form" in html
    assert "student-stepper" in html
    assert 'data-step="1"' in html
    assert 'data-step="2"' in html
    assert 'data-step="3"' in html
    assert 'data-step="4"' in html
    assert "Step 1 of 4" in html
    assert 'name="academic_session"' in html
    assert 'name="batch"' in html
    assert "Academic Session / Batch" not in html
    print("✓ Student registration page loads with 4-step wizard")


def test_organizer_registration_page_loads(client):
    """Test that organizer registration page loads with stepper."""
    response = client.get("/register/organizer")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "organizer-register-form" in html
    assert "organizer-stepper" in html
    assert 'data-step="1"' in html
    assert 'data-step="2"' in html
    assert 'data-step="3"' in html
    assert "Step 1 of 3" in html
    print("✓ Organizer registration page loads with 3-step wizard")


def test_faculty_registration_page_loads(client):
    """Test that faculty registration page loads with stepper."""
    response = client.get("/register/faculty")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "faculty-register-form" in html
    assert "faculty-stepper" in html
    assert 'data-step="1"' in html
    assert 'data-step="2"' in html
    assert 'data-step="3"' in html
    assert "Step 1 of 3" in html
    print("✓ Faculty registration page loads with 3-step wizard")


def test_validate_step_student_step1_valid(client):
    """Test validating student step 1 with valid data."""
    response = client.post("/api/register/validate-step", data={
        "role": "student",
        "step": "1",
        "name": "John Doe",
        "email": "john@example.com",
        "mobile": "+91 98765 43210",
    })
    assert response.status_code == 200
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is True
    print("✓ Student step 1 validation passes with valid data")


def test_validate_step_student_step1_missing_fields(client):
    """Test validating student step 1 with missing required fields."""
    response = client.post("/api/register/validate-step", data={
        "role": "student",
        "step": "1",
        "name": "",
        "email": "",
    })
    assert response.status_code == 400
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is False
    assert "errors" in data
    print("✓ Student step 1 validation fails with missing fields")


def test_validate_step_student_step2_valid(client):
    """Test validating student step 2 with valid data."""
    response = client.post("/api/register/validate-step", data={
        "role": "student",
        "step": "2",
        "student_id": "21CS1001",
        "roll_no": "21CS1001",
    })
    assert response.status_code == 200
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is True
    print("✓ Student step 2 validation passes with valid data")


def test_validate_step_student_step2_missing_fields(client):
    """Test validating student step 2 with missing fields."""
    response = client.post("/api/register/validate-step", data={
        "role": "student",
        "step": "2",
        "student_id": "",
    })
    assert response.status_code == 400
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is False
    assert "student_id" in data["errors"]
    print("✓ Student step 2 validation fails with missing student_id")


def test_validate_step_student_step3_valid(client):
    """Test validating student step 3 with valid data."""
    response = client.post("/api/register/validate-step", data={
        "role": "student",
        "step": "3",
        "course": "B.Tech",
        "semester": "1",
        "academic_session": "2025–2026",
        "batch": "2025",
    })
    assert response.status_code == 200
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is True
    print("✓ Student step 3 validation passes with valid data")


def test_validate_step_student_step4_valid(client):
    """Test validating student step 4 with valid password data."""
    response = client.post("/api/register/validate-step", data={
        "role": "student",
        "step": "4",
        "password": "Pass123!@#",
        "confirm_password": "Pass123!@#",
    })
    assert response.status_code == 200
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is True
    print("✓ Student step 4 validation passes with valid passwords")


def test_validate_step_organizer_step1_valid(client):
    """Test validating organizer step 1."""
    response = client.post("/api/register/validate-step", data={
        "role": "organizer",
        "step": "1",
        "name": "Jane Org",
        "email": "jane@example.com",
        "mobile": "+91 98765 43211",
    })
    assert response.status_code == 200
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is True
    print("✓ Organizer step 1 validation passes")


def test_validate_step_organizer_step2_valid(client):
    """Test validating organizer step 2."""
    response = client.post("/api/register/validate-step", data={
        "role": "organizer",
        "step": "2",
        "employee_id": "AGC-ORG-1001",
    })
    assert response.status_code == 200
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is True
    print("✓ Organizer step 2 validation passes")


def test_validate_step_organizer_step3_valid(client):
    """Test validating organizer step 3."""
    response = client.post("/api/register/validate-step", data={
        "role": "organizer",
        "step": "3",
        "password": "Org123!@#",
        "confirm_password": "Org123!@#",
    })
    assert response.status_code == 200
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is True
    print("✓ Organizer step 3 validation passes")


def test_validate_step_faculty_step1_valid(client):
    """Test validating faculty step 1."""
    response = client.post("/api/register/validate-step", data={
        "role": "faculty",
        "step": "1",
        "name": "Dr. Smith",
        "email": "dr.smith@example.com",
        "mobile": "+91 98765 43212",
    })
    assert response.status_code == 200
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is True
    print("✓ Faculty step 1 validation passes")


def test_validate_step_faculty_step2_valid(client):
    """Test validating faculty step 2."""
    response = client.post("/api/register/validate-step", data={
        "role": "faculty",
        "step": "2",
        "employee_id": "AGC-FAC-1001",
    })
    assert response.status_code == 200
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is True
    print("✓ Faculty step 2 validation passes")


def test_validate_step_faculty_step3_valid(client):
    """Test validating faculty step 3."""
    response = client.post("/api/register/validate-step", data={
        "role": "faculty",
        "step": "3",
        "password": "Fac123!@#",
        "confirm_password": "Fac123!@#",
    })
    assert response.status_code == 200
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is True
    print("✓ Faculty step 3 validation passes")


def test_validate_step_invalid_role(client):
    """Test validating step with invalid role."""
    response = client.post("/api/register/validate-step", data={
        "role": "invalid_role",
        "step": "1",
    })
    assert response.status_code == 400
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is False
    print("✓ Invalid role returns error")


def test_validate_step_invalid_step(client):
    """Test validating step with invalid step number."""
    response = client.post("/api/register/validate-step", data={
        "role": "student",
        "step": "99",
    })
    assert response.status_code == 400
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is False
    print("✓ Invalid step returns error")


def test_save_step_session(client):
    """Test saving step data to session."""
    response = client.post("/api/register/save-step", data={
        "role": "student",
        "step": "1",
        "name": "Test User",
        "email": "test@example.com",
    })
    assert response.status_code == 200
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is True
    print("✓ Step data saved to session")


def test_restore_step_session(client):
    """Test restoring step data from session."""
    client.post("/api/register/save-step", data={
        "role": "student",
        "step": "1",
        "name": "Restore User",
        "email": "restore@example.com",
    })
    response = client.post("/api/register/restore-step", data={
        "role": "student",
        "step": "1",
    })
    assert response.status_code == 200
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is True
    assert data["data"]["name"] == "Restore User"
    assert data["data"]["email"] == "restore@example.com"
    print("✓ Step data restored from session")


def test_clear_session(client):
    """Test clearing session data."""
    client.post("/api/register/save-step", data={
        "role": "student",
        "step": "1",
        "name": "Temp User",
    })
    response = client.post("/api/register/clear-session")
    assert response.status_code == 200
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is True
    response2 = client.post("/api/register/restore-step", data={
        "role": "student",
        "step": "1",
    })
    restored = json.loads(response2.get_data(as_text=True))
    assert restored["data"] == {}
    print("✓ Session data cleared successfully")


def test_student_full_registration(client):
    """Test complete student registration via the main route."""
    response = client.post("/register/student", data={
        "name": "Full Test Student",
        "email": "fulltest@example.com",
        "mobile": "+91 98765 43213",
        "date_of_birth": "2000-01-15",
        "student_id": "21CS9999",
        "roll_no": "21CS9999",
        "course": "B.Tech",
        "department": "Computer Science",
        "semester": "1",
        "academic_session": "2025–2026",
        "batch": "2025",
        "password": "Test123!@#",
        "confirm_password": "Test123!@#",
    })
    assert response.status_code in (200, 302)
    if response.status_code == 200:
        data = json.loads(response.get_data(as_text=True))
        assert data["success"] is True, f"Registration failed: {data}"
    print("✓ Full student registration completes successfully")


def test_organizer_full_registration(client):
    """Test complete organizer registration."""
    response = client.post("/register/organizer", data={
        "name": "Full Test Organizer",
        "email": "organizer@example.com",
        "mobile": "+91 98765 43214",
        "employee_id": "AGC-ORG-9999",
        "department": "Student Affairs",
        "password": "Org123!@#",
        "confirm_password": "Org123!@#",
    })
    assert response.status_code in (200, 302)
    if response.status_code == 200:
        data = json.loads(response.get_data(as_text=True))
        assert data["success"] is True, f"Registration failed: {data}"
    print("✓ Full organizer registration completes successfully")


def test_faculty_full_registration(client):
    """Test complete faculty registration."""
    response = client.post("/register/faculty", data={
        "name": "Dr. Full Faculty",
        "email": "faculty@example.com",
        "mobile": "+91 98765 43215",
        "employee_id": "AGC-FAC-9999",
        "department": "Computer Science",
        "designation": "Assistant Professor",
        "password": "Fac123!@#",
        "confirm_password": "Fac123!@#",
    })
    assert response.status_code in (200, 302)
    if response.status_code == 200:
        data = json.loads(response.get_data(as_text=True))
        assert data["success"] is True, f"Registration failed: {data}"
    print("✓ Full faculty registration completes successfully")


def test_duplicate_email_registration(client):
    """Test that duplicate email registration fails."""
    client.post("/register/student", data={
        "name": "Dup Test",
        "email": "dup@example.com",
        "mobile": "+91 98765 43216",
        "student_id": "21CS8888",
        "roll_no": "21CS8888",
        "course": "B.Tech",
        "semester": "1",
        "academic_session": "2025–2026",
        "batch": "2025",
        "password": "Test123!@#",
        "confirm_password": "Test123!@#",
    })
    response = client.post("/register/student", data={
        "name": "Dup Test 2",
        "email": "dup@example.com",
        "mobile": "+91 98765 43217",
        "student_id": "21CS7777",
        "roll_no": "21CS7777",
        "course": "B.Tech",
        "semester": "1",
        "academic_session": "2025–2026",
        "batch": "2025",
        "password": "Test123!@#",
        "confirm_password": "Test123!@#",
    })
    assert response.status_code == 400
    data = json.loads(response.get_data(as_text=True))
    assert "email" in data["errors"]
    print("✓ Duplicate email registration is rejected")


def test_student_step_validation_server_side(client):
    """Test that server-side step validation catches errors specific to each step."""
    response = client.post("/api/register/validate-step", data={
        "role": "student",
        "step": "1",
        "name": "",
        "email": "invalid-email",
        "mobile": "",
    })
    assert response.status_code == 400
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is False
    assert "name" in data["errors"]
    assert "email" in data["errors"]
    print("✓ Step 1 server-side validation catches errors")

    response = client.post("/api/register/validate-step", data={
        "role": "student",
        "step": "2",
        "student_id": "",
        "roll_no": "",
    })
    assert response.status_code == 400
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is False
    assert "student_id" in data["errors"]
    assert "roll_no" in data["errors"]
    print("✓ Step 2 server-side validation catches errors")

    response = client.post("/api/register/validate-step", data={
        "role": "student",
        "step": "3",
        "course": "",
        "semester": "",
        "academic_session": "",
        "batch": "",
    })
    assert response.status_code == 400
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is False
    assert "course" in data["errors"]
    assert "semester" in data["errors"]
    assert "academic_session" in data["errors"]
    assert "batch" in data["errors"]
    print("✓ Step 3 server-side validation catches errors")

    response = client.post("/api/register/validate-step", data={
        "role": "student",
        "step": "4",
        "password": "short",
        "confirm_password": "different",
    })
    assert response.status_code == 400
    data = json.loads(response.get_data(as_text=True))
    assert data["success"] is False
    assert "password" in data["errors"]
    print("✓ Step 4 server-side validation catches password errors")


def run_all_tests():
    client = setup_app()

    tests = [
        test_student_registration_page_loads,
        test_organizer_registration_page_loads,
        test_faculty_registration_page_loads,
        test_validate_step_student_step1_valid,
        test_validate_step_student_step1_missing_fields,
        test_validate_step_student_step2_valid,
        test_validate_step_student_step2_missing_fields,
        test_validate_step_student_step3_valid,
        test_validate_step_student_step4_valid,
        test_validate_step_organizer_step1_valid,
        test_validate_step_organizer_step2_valid,
        test_validate_step_organizer_step3_valid,
        test_validate_step_faculty_step1_valid,
        test_validate_step_faculty_step2_valid,
        test_validate_step_faculty_step3_valid,
        test_validate_step_invalid_role,
        test_validate_step_invalid_step,
        test_save_step_session,
        test_restore_step_session,
        test_clear_session,
        test_student_full_registration,
        test_organizer_full_registration,
        test_faculty_full_registration,
        test_duplicate_email_registration,
        test_student_step_validation_server_side,
    ]

    passed = 0
    failed = 0
    errors = []

    for test in tests:
        try:
            test(client)
            passed += 1
        except AssertionError as e:
            failed += 1
            errors.append(f"FAIL: {test.__name__}: {e}")
            print(f"  → {e}")
        except Exception as e:
            failed += 1
            errors.append(f"ERROR: {test.__name__}: {e}")
            print(f"  → ERROR: {e}")

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    if errors:
        print("\nFailures:")
        for err in errors:
            print(f"  {err}")
    else:
        print("\nAll tests passed! ✓")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
