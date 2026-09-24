import os
os.environ['DATABASE_URL'] = 'sqlite:///test_faculty.db'
os.environ['SECRET_KEY'] = 'test-secret'

from app import app, db

with app.app_context():
    db.drop_all()
    db.create_all()
    client = app.test_client()
    
    # Test 1: GET /register/faculty
    resp = client.get('/register/faculty')
    print(f'GET /register/faculty: {resp.status_code}')
    html = resp.get_data(as_text=True)
    
    # Check which template is rendered
    if 'Faculty Registration' in html:
        print('  -> Renders faculty_register.html (CORRECT)')
    elif 'Student Registration' in html:
        print('  -> Renders student_register.html (BUG!)')
    else:
        print('  -> Unknown template')
    
    # Check for faculty fields
    faculty_fields = ['employee_id', 'faculty_role', 'designation', 'academic_session']
    for f in faculty_fields:
        present = f'name="{f}"' in html
        print(f'  Has {f}: {present}')
    
    # Check for student fields (should NOT be present)
    student_fields = ['student_id', 'roll_no', 'course', 'semester', 'section']
    for f in student_fields:
        present = f'name="{f}"' in html
        print(f'  Has {f} (should be False): {present}')