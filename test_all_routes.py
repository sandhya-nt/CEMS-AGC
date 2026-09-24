import os
os.environ['FLASK_DEBUG'] = '0'
os.environ['FLASK_ENV'] = 'development'

from app import app, db

app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False

client = app.test_client()

# Test all routes - login as student first
resp = client.post('/login', data={'email': 'student@agc.local', 'password': 'Student@123'})
print(f"Login as student: {resp.status_code}")

# Now test all routes
routes_to_test = [
    ('GET', '/'),
    ('GET', '/login'),
    ('GET', '/register'),
    ('GET', '/register/student'),
    ('GET', '/register/faculty'),
    ('GET', '/register/organizer'),
    ('GET', '/login/student'),
    ('GET', '/organizer/login'),
    ('GET', '/faculty/login'),
    ('GET', '/dashboard'),
    ('GET', '/student/dashboard'),
    ('GET', '/events'),
    ('GET', '/events/1'),
    ('GET', '/profile'),
    ('GET', '/student/events'),
    ('GET', '/student/registrations'),
    ('GET', '/student/tickets'),
    ('GET', '/student/notifications'),
    ('GET', '/student/feedback'),
    ('GET', '/student/certificates'),
    ('GET', '/past-events'),
    ('GET', '/past-events/1'),
    ('GET', '/notices'),
    ('GET', '/search'),
    ('GET', '/contact'),
    ('GET', '/about'),
    ('GET', '/health'),
    ('GET', '/student/events/1/waitlist'),
    ('GET', '/student/events/1/lifecycle'),
    ('GET', '/student/events/1/gallery'),
    ('GET', '/student/events/1/documents'),
    ('GET', '/student/events/1/cancel'),
    ('GET', '/registration/1/feedback'),
    ('GET', '/registration/1/result'),
    ('GET', '/ticket/1'),
    ('GET', '/ticket/1/download'),
    ('GET', '/ticket/1/qr'),
    ('GET', '/certificate/1'),
    ('GET', '/certificate/preview/1'),
    ('GET', '/api/notifications'),
    ('GET', '/api/events/1/validate-registration'),
    ('GET', '/api/admin/dashboard'),
    ('GET', '/api/organizer/dashboard-stats'),
    ('GET', '/api/teacher/registrations'),
    ('GET', '/api/teacher/dashboard'),
]

errors = []
for method, path in routes_to_test:
    try:
        if method == 'GET':
            resp = client.get(path)
        else:
            resp = client.post(path)
        status = resp.status_code
        if status == 500:
            body = resp.data.decode('utf-8', errors='replace')
            # Try to find the error
            import re
            # Look for Jinja2 or Python error
            jinja_err = re.search(r'(UndefinedError|TemplateNotFound|Jinja|jinja2[^\n]+)', body)
            py_err = re.search(r'(Error|Exception|Traceback)[^\n<]{0,200}', body)
            err_msg = ""
            if jinja_err:
                err_msg = jinja_err.group()[:200]
            elif py_err:
                err_msg = py_err.group()[:200]
            else:
                # Look for error in the body
                err_match = re.search(r'<!-- ERROR: ([^<]+)', body)
                if err_match:
                    err_msg = err_match.group(1)[:200]
                else:
                    err_msg = body[:200].replace('\n', ' ')
            errors.append((method, path, status, err_msg))
            print(f"  {method} {path} => {status} ERROR: {err_msg}")
        else:
            print(f"  {method} {path} => {status}")
    except Exception as e:
        print(f"  {method} {path} => EXCEPTION: {e}")
        errors.append((method, path, 'EXC', str(e)[:200]))

print(f"\n=== {len(errors)} ERRORS FOUND ===")
for method, path, status, err in errors:
    print(f"  {method} {path} => {status}: {err}")
