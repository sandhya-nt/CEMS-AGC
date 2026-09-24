import os
import re
os.environ['DATABASE_URL'] = 'sqlite:///test_faculty.db'
os.environ['SECRET_KEY'] = 'test-secret'

from app import app, db

with app.app_context():
    db.drop_all()
    db.create_all()
    client = app.test_client()
    
    def get_csrf_token(url):
        resp = client.get(url)
        html = resp.get_data(as_text=True)
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
        return match.group(1) if match else None
    
    # Get CSRF token for faculty registration
    csrf_token = get_csrf_token('/register/faculty')
    print(f'CSRF token: {csrf_token[:30]}...' if csrf_token else 'No CSRF token!')
    
    # Test POST /register/faculty with valid data but no date_of_birth
    resp = client.post('/register/faculty', 
        data={
            'csrf_token': csrf_token,
            'name': 'Dr. Jane Smith',
            'email': 'jane.smith@faculty.agc.edu',
            'mobile': '9876543210',
            'employee_id': 'FAC-001',
            'department': 'Computer Science',
            'designation': 'Assistant Professor',
            'faculty_role': 'Faculty Member',
            'academic_session': '2025-2026',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'role': 'faculty',
        },
        content_type='multipart/form-data',
        headers={'X-Requested-With': 'XMLHttpRequest'})
    
    print(f'\nPOST /register/faculty (no date_of_birth): {resp.status_code}')
    if resp.is_json:
        result = resp.get_json()
        print(f'  Success: {result.get("success")}')
        print(f'  Errors: {result.get("errors")}')
    else:
        print(f'  Response (first 500 chars): {resp.get_data(as_text=True)[:500]}')
    
    # Get new CSRF token (since session changed)
    csrf_token2 = get_csrf_token('/register/faculty')
    
    # Test with date_of_birth added
    resp2 = client.post('/register/faculty', 
        data={
            'csrf_token': csrf_token2,
            'name': 'Dr. John Doe',
            'email': 'john.doe@faculty.agc.edu',
            'mobile': '9876543211',
            'employee_id': 'FAC-002',
            'department': 'Physics',
            'designation': 'Professor',
            'faculty_role': 'Faculty Member',
            'academic_session': '2025-2026',
            'date_of_birth': '1980-01-15',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'role': 'faculty',
        },
        content_type='multipart/form-data',
        headers={'X-Requested-With': 'XMLHttpRequest'})
    
    print(f'\nPOST /register/faculty (with date_of_birth): {resp2.status_code}')
    if resp2.is_json:
        result = resp2.get_json()
        print(f'  Success: {result.get("success")}')
        print(f'  Errors: {result.get("errors")}')
        if result.get('success'):
            # Check if FacultyProfile was created
            from cems.domain import FacultyProfile, User
            user = User.query.filter_by(email='john.doe@faculty.agc.edu').first()
            if user:
                fp = FacultyProfile.query.filter_by(user_id=user.id).first()
                print(f'  User role: {user.role}')
                print(f'  FacultyProfile created: {fp is not None}')
                if fp:
                    print(f'  FacultyProfile.employee_id: {fp.employee_id}')
                    print(f'  FacultyProfile.faculty_role: {fp.faculty_role}')
                    print(f'  FacultyProfile.designation: {fp.designation}')
                    print(f'  FacultyProfile.academic_session: {fp.academic_session}')
    else:
        print(f'  Response (first 500 chars): {resp2.get_data(as_text=True)[:500]}')