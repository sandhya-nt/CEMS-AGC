import urllib.request, urllib.parse, http.cookiejar, re, json

BASE = 'http://127.0.0.1:5557'
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def fetch(url, method='GET', data=None, headers=None):
    hdrs = headers or {}
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    for k, v in hdrs.items():
        req.add_header(k, v)
    try:
        resp = opener.open(req, timeout=15)
        return resp.status, resp.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='replace')

# 1. GET login page, get CSRF
status, body = fetch(BASE + '/login')
print(f'GET /login => {status}')
csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', body)
if not csrf_match:
    print('NO CSRF TOKEN FOUND in login page!')
    print('Login page body:', body[:500])
    raise SystemExit(1)
csrf = csrf_match.group(1)
print(f'CSRF token: {csrf[:30]}...')

# 2. POST login as student
status, body = fetch(BASE + '/login', method='POST', data={'email': 'student@agc.local', 'password': 'Student@123', 'csrf_token': csrf})
print(f'POST /login (student) => {status}')
if status == 500:
    print('ERROR:', body[:1000])

# 3. GET student dashboard
status, body = fetch(BASE + '/student/dashboard')
print(f'\nGET /student/dashboard => {status}')
if status == 500:
    print('ERROR BODY:', body[:1500])

# 4. GET profile
status, body = fetch(BASE + '/profile')
print(f'GET /profile => {status}')
if status == 500:
    print('ERROR BODY:', body[:1500])

# 5. GET register/student
status, body = fetch(BASE + '/register/student')
print(f'\nGET /register/student => {status}')
if status == 500:
    print('ERROR BODY:', body[:1500])

# 6. POST to register/student
csrf_match2 = re.search(r'name="csrf_token" value="([^"]+)"', body)
csrf2 = csrf_match2.group(1) if csrf_match2 else csrf
status, body = fetch(BASE + '/register/student', method='POST', data={
    'role': 'student',
    'name': 'Test Student Reg',
    'email': 'teststudent4@agc.local',
    'mobile': '9876543210',
    'password': 'Test@1234',
    'confirm_password': 'Test@1234',
    'student_id': 'STU2024099',
    'roll_no': 'CSE2024099',
    'department': 'Computer Science',
    'course': 'B.Tech Computer Science',
    'semester': '5',
    'academic_session': '2024-2025',
    'batch': '2024',
    'section': 'A',
    'date_of_birth': '2002-05-15',
    'gender': 'male',
    'csrf_token': csrf2,
})
print(f'POST /register/student => {status}')
if status == 500:
    print('ERROR BODY:', body[:1500])
elif status == 200:
    if 'error' in body.lower() or 'Invalid' in body or 'already' in body:
        print('Registration returned errors')
        print(body[:500])
    else:
        print('Registration seems successful')
        print(body[:200])
