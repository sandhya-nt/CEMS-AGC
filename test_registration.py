import urllib.request
import urllib.parse
import http.cookiejar
import re
import json

BASE = "http://127.0.0.1:5555"
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj), urllib.request.HTTPRedirectHandler())

def fetch(url, method="GET", data=None, headers=None, raw_body=None):
    hdrs = headers or {}
    body = None
    if raw_body is not None:
        body = raw_body.encode() if isinstance(raw_body, str) else raw_body
    elif data is not None:
        body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method=method)
    for k, v in hdrs.items():
        req.add_header(k, v)
    try:
        resp = opener.open(req, timeout=15)
        return resp.status, resp.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='replace')

# Step 1: GET /register/student to get CSRF token
status, body = fetch(BASE + "/register/student")
print(f"GET /register/student => {status}")
csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', body)
if not csrf_match:
    # Try to find it in a meta tag or other format
    csrf_match = re.search(r'"csrf_token":"([^"]+)"', body)
if not csrf_match:
    print("NO CSRF TOKEN found in register page!")
    # Try api_register instead
    sys_exit = True
else:
    csrf_token = csrf_match.group(1)

# Step 2: GET /api/register/save-step to check session step
# Let's try to register via the API
status, body = fetch(BASE + "/api/register/clear-session", method="POST")
print(f"POST /api/register/clear-session => {status}")

# Step 3: Try saving step 1 (personal info)
step1_data = json.dumps({
    "step": "personal",
    "name": "Test Student",
    "email": "teststudent@agc.local",
    "mobile": "9876543210",
    "date_of_birth": "2002-05-15",
    "gender": "male",
    "password": "Test@1234",
    "confirm_password": "Test@1234",
}).encode()

status, body = fetch(BASE + "/api/register/save-step", method="POST", headers={"Content-Type": "application/json", "X-CSRFToken": csrf_token}, raw_body=json.dumps({
    "step": "personal",
    "name": "Test Student",
    "email": "teststudent@agc.local",
    "mobile": "9876543210",
    "date_of_birth": "2002-05-15",
    "gender": "male",
    "password": "Test@1234",
    "confirm_password": "Test@1234",
}))
print(f"\nPOST /api/register/save-step (personal) => {status}")
if status != 200:
    print(f"  BODY: {body[:500]}")

# Step 4: Save step 2 (student info)
status, body = fetch(BASE + "/api/register/save-step", method="POST", headers={"Content-Type": "application/json", "X-CSRFToken": csrf_token}, raw_body=json.dumps({
    "step": "student_info",
    "student_id": "STU2024001",
    "roll_no": "CSE2024001",
    "department": "Computer Science",
    "course": "B.Tech Computer Science",
    "semester": "5",
    "academic_session": "2024-2025",
    "batch": "2024",
    "section": "A",
}))
print(f"POST /api/register/save-step (student_info) => {status}")
if status != 200:
    print(f"  BODY: {body[:500]}")

# Step 5: Validate step
status, body = fetch(BASE + "/api/register/validate-step", method="POST", headers={"Content-Type": "application/json", "X-CSRFToken": csrf_token}, raw_body=json.dumps({
    "step": "student_info",
    "student_id": "STU2024001",
    "roll_no": "CSE2024001",
    "department": "Computer Science",
    "course": "B.Tech Computer Science",
    "semester": "5",
    "academic_session": "2024-2025",
    "batch": "2024",
    "section": "A",
}))
print(f"\nPOST /api/register/validate-step (student_info) => {status}")
print(f"  BODY: {body[:500]}")

# Step 6: Try full registration via POST form
status, body = fetch(BASE + "/register/student", method="POST", data={
    "role": "student",
    "name": "Form Student",
    "email": "formstudent@agc.local",
    "mobile": "9876543211",
    "password": "Test@1234",
    "confirm_password": "Test@1234",
    "student_id": "STU2024002",
    "roll_no": "CSE2024002",
    "department": "Computer Science",
    "course": "B.Tech Computer Science",
    "semester": "5",
    "academic_session": "2024-2025",
    "batch": "2024",
    "section": "A",
    "date_of_birth": "2002-05-15",
    "gender": "male",
    "csrf_token": csrf_token,
})
print(f"\nPOST /register/student (form) => {status}")
if status == 500:
    print(f"  ERROR: {body[:1000]}")
elif status == 302 or status == 200:
    if "Welcome" in body or "dashboard" in body.lower():
        print("  Registration appears successful")
    else:
        print(f"  BODY: {body[:300]}")
