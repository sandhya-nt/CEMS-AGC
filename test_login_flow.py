import urllib.request
import urllib.parse
import http.cookiejar
import re
import sys

BASE = "http://127.0.0.1:5555"

# Set up cookie jar to persist session
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def fetch(url, method="GET", data=None, headers=None):
    hdrs = headers or {}
    if data is not None and isinstance(data, dict):
        data = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in hdrs.items():
        req.add_header(k, v)
    try:
        resp = opener.open(req, timeout=15)
        return resp.status, resp.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='replace')

# Step 1: GET login page to extract CSRF token
status, body = fetch(BASE + "/login")
print(f"GET /login => {status}")

csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', body)
if csrf_match:
    csrf_token = csrf_match.group(1)
    print(f"CSRF token found: {csrf_token[:20]}...")
else:
    print("NO CSRF TOKEN FOUND!")
    # Try api login pattern
    sys.exit(1)

# Step 2: POST login with student credentials
login_data = {
    "email": "student@agc.local",
    "password": "Student@123",
    "csrf_token": csrf_token,
}
status, body = fetch(BASE + "/login", method="POST", data=login_data)
print(f"POST /login (student) => {status}")
if status == 500:
    print("ERROR BODY:", body[:500])
elif status == 200 and "Invalid" in body:
    print("LOGIN FAILED:", body[:300])
else:
    # Check redirect
    if "Welcome back" in body or "dashboard" in body.lower() or status == 200:
        print("Login appears successful or redirected")

# Step 3: Access student dashboard
status, body = fetch(BASE + "/student/dashboard")
print(f"\nGET /student/dashboard => {status}")
if status == 500:
    # Extract error
    err_match = re.search(r'(?:Error|error|Exception|Traceback).*', body, re.DOTALL)
    print("ERROR BODY:")
    print(body[:1000])
elif status == 403:
    print("403 Forbidden - may be role issue")
    print(body[:300])
else:
    print(f"Page length: {len(body)} chars")

# Step 4: Access profile page
status, body = fetch(BASE + "/profile")
print(f"\nGET /profile => {status}")
if status == 500:
    print("ERROR BODY:")
    print(body[:1000])
elif status == 403:
    print("403 Forbidden")
else:
    print(f"Page length: {len(body)} chars")
    if "StudentProfile" in body:
        print("Page contains StudentProfile reference")
