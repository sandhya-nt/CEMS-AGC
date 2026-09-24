import os
import re
os.environ['DATABASE_URL'] = 'sqlite:///test_faculty_e2e.db'
os.environ['SECRET_KEY'] = 'test-secret'

from app import app, db, User
from cems.domain import FacultyProfile

with app.app_context():
    db.drop_all()
    db.create_all()
    client = app.test_client()
    
    def get_csrf_token(url):
        resp = client.get(url)
        html = resp.get_data(as_text=True)
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
        return match.group(1) if match else None
    
    print("=" * 60)
    print("END-TO-END FACULTY REGISTRATION TEST")
    print("=" * 60)
    
    # Test 1: GET /register/faculty
    print("\n1. Testing GET /register/faculty")
    resp = client.get('/register/faculty')
    print(f"   Status: {resp.status_code}")
    html = resp.get_data(as_text=True)
    
    # Verify correct template
    if 'Faculty Registration' in html:
        print("   [OK] Renders faculty_register.html")
    else:
        print("   [FAIL] WRONG TEMPLATE!")
    
    # Verify faculty fields present
    faculty_fields = ['employee_id', 'faculty_role', 'designation', 'academic_session']
    for f in faculty_fields:
        present = f'name="{f}"' in html
        print(f"   [{'OK' if present else 'FAIL'}] Has {f} field: {present}")
    
    # Verify student fields NOT present
    student_fields = ['student_id', 'roll_no', 'course', 'semester', 'section']
    for f in student_fields:
        present = f'name="{f}"' in html
        print(f"   [{'OK' if not present else 'FAIL'}] No {f} field: {not present}")
    
    # Test 2: POST /register/faculty with valid data
    print("\n2. Testing POST /register/faculty (valid data)")
    csrf_token = get_csrf_token('/register/faculty')
    faculty_data = {
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
    }
    resp = client.post('/register/faculty', 
        data=faculty_data,
        content_type='multipart/form-data',
        headers={'X-Requested-With': 'XMLHttpRequest'})
    
    print(f"   Status: {resp.status_code}")
    if resp.is_json:
        result = resp.get_json()
        print(f"   Success: {result.get('success')}")
        print(f"   Errors: {result.get('errors')}")
        if result.get('success'):
            print("   ✓ Faculty registration successful")
        else:
            print("   ✗ Faculty registration failed")
    else:
        print(f"   ✗ Non-JSON response: {resp.get_data(as_text=True)[:200]}")
    
    # Test 3: Verify database records
    print("\n3. Verifying database records")
    user = User.query.filter_by(email='jane.smith@faculty.agc.edu').first()
    if user:
        print(f"   ✓ User created: {user.name} (ID: {user.id})")
        print(f"   ✓ User role: {user.role}")
        print(f"   ✓ User department: {user.department}")
        print(f"   ✓ User employee_id: {user.employee_id}")
        print(f"   ✓ User student_id: {user.student_id} (should be None)")
        print(f"   ✓ User roll_no: {user.roll_no} (should be None)")
        
        fp = FacultyProfile.query.filter_by(user_id=user.id).first()
        if fp:
            print(f"   ✓ FacultyProfile created")
            print(f"   ✓ FacultyProfile.employee_id: {fp.employee_id}")
            print(f"   ✓ FacultyProfile.faculty_role: {fp.faculty_role}")
            print(f"   ✓ FacultyProfile.designation: {fp.designation}")
            print(f"   ✓ FacultyProfile.academic_session: {fp.academic_session}")
            print(f"   ✓ FacultyProfile.department: {fp.department}")
        else:
            print("   ✗ FacultyProfile NOT created!")
        
        # Verify NO StudentProfile
        from cems.domain import StudentProfile
        sp = StudentProfile.query.filter_by(user_id=user.id).first()
        if sp:
            print("   ✗ StudentProfile incorrectly created!")
        else:
            print("   ✓ No StudentProfile created (correct)")
    else:
        print("   ✗ User not found in database!")
    
    # Test 4: Login as faculty
    print("\n4. Testing faculty login")
    csrf_token2 = get_csrf_token('/login')
    resp = client.post('/login', 
        data={
            'email': 'jane.smith@faculty.agc.edu',
            'password': 'Password123!',
        },
        follow_redirects=True)
    
    print(f"   Login status: {resp.status_code}")
    # Check redirect to teacher dashboard
    resp_dash = client.get('/dashboard')
    print(f"   Dashboard redirect status: {resp_dash.status_code}")
    if resp_dash.status_code in (301, 302, 303, 308):
        loc = resp_dash.headers.get('Location', '')
        print(f"   Redirect location: {loc}")
        if 'teacher' in loc:
            print("   ✓ Redirects to teacher dashboard")
        else:
            print("   ✗ Does not redirect to teacher dashboard")
    
    # Test 5: Access teacher dashboard
    print("\n5. Testing teacher dashboard access")
    resp = client.get('/teacher/dashboard')
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        print("   ✓ Teacher dashboard accessible")
        html = resp.get_data(as_text=True)
        if 'Dashboard' in html:
            print("   ✓ Dashboard content loads")
        else:
            print("   ✗ Dashboard content missing")
    else:
        print("   ✗ Teacher dashboard not accessible")
    
    # Test 6: Switching account types (no contamination)
    print("\n6. Testing account type switching (no contamination)")
    client.get('/logout')
    
    # Student form
    resp = client.get('/register/student')
    html_stu = resp.get_data(as_text=True)
    stu_fields = ['student_id', 'roll_no', 'course']
    for f in stu_fields:
        present = f'name="{f}"' in html_stu
        print(f"   Student form has {f}: {present}")
    
    # Faculty form
    resp = client.get('/register/faculty')
    html_fac = resp.get_data(as_text=True)
    fac_fields = ['employee_id', 'faculty_role', 'designation']
    for f in fac_fields:
        present = f'name="{f}"' in html_fac
        print(f"   Faculty form has {f}: {present}")
    
    # Verify no cross-contamination
    stu_in_fac = ['student_id', 'roll_no', 'course']
    for f in stu_in_fac:
        present = f'name="{f}"' in html_fac
        print(f"   Faculty form has NO {f}: {not present}")
    
    print("\n" + "=" * 60)
    print("END-TO-END TEST COMPLETE")
    print("=" * 60)