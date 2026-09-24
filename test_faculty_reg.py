import re
from app import app, db, User

with app.test_client() as c:
    # First GET the page to get CSRF token
    r = c.get('/register/faculty')
    print(f'GET /register/faculty: {r.status_code}')
    
    # Extract CSRF token from response
    csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', r.get_data(as_text=True))
    if csrf_match:
        csrf_token = csrf_match.group(1)
        print(f'CSRF token: {csrf_token[:20]}...')
        
        # Test faculty registration POST with CSRF token
        data = {
            'name': 'Test Faculty',
            'email': 'testfaculty@agc.edu.in',
            'mobile': '+91 98765 43210',
            'employee_id': 'AGC-FAC-1001',
            'department': 'Computer Science',
            'designation': 'Assistant Professor',
            'faculty_role': 'Faculty Member',
            'academic_session': '2025-2026',
            'password': 'Faculty@123',
            'confirm_password': 'Faculty@123',
            'role': 'faculty',
            'csrf_token': csrf_token
        }
        r = c.post('/register/faculty', data=data, headers={'X-Requested-With': 'XMLHttpRequest'})
        print(f'POST /register/faculty: {r.status_code}')
        print(f'Response: {r.get_json()}')
        
        # Check if user was created
        user = User.query.filter_by(email='testfaculty@agc.edu.in').first()
        if user:
            print(f'User created: {user.name}, role: {user.role}, employee_id: {user.employee_id}')
        else:
            print('User not found in DB')
    else:
        print('CSRF token not found in response')