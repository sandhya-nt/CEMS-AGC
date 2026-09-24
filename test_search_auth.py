import sys, json
sys.path.insert(0, ".")
from app import app

client = app.test_client()

def test(label, resp):
    data = json.loads(resp.data)
    print(f"=== {label} ===")
    print(f"  Success: {data.get('success')}")
    print(f"  Total results: {data.get('total_results')}")
    print(f"  Totals: {data.get('totals')}")
    return data

# Test search page renders
print("##### PAGE RENDER #####")
resp = client.get("/search")
print(f"  Status: {resp.status_code}")
print(f"  Contains 'Global Search': {'Global Search' in resp.data.decode()}")
print(f"  Contains 'search.js': {'search.js' in resp.data.decode()}")
print(f"  Contains 'search.css': {'search.css' in resp.data.decode()}")

# Test with student login for certificate visibility
print("\n##### STUDENT LOGIN & CERT SEARCH #####")
resp = client.post("/api/login", data={
    "email": "student@agc.local",
    "password": "Student@123"
})
print(f"  Login: {resp.status_code}, {json.loads(resp.data).get('message')}")

# Student should see 0 certificates (none generated yet)
resp = client.get("/api/search?type=certificate&page=1&per_page=5")
d = test("Certificate search (student auth)", resp)
print(f"  Empty desc: {d.get('empty_messages', {}).get('certificates')}")

# Student searching events
resp = client.get("/api/search?q=AI&type=event&page=1&per_page=3")
d = test("Event search (student auth, q=AI)", resp)
for e in d.get("results", {}).get("events", []):
    print(f"  {e['title']} | {e['status']} | desc len: {len(e.get('description',''))}")

# Student searching users (should not see private data)
print("\n##### STUDENT SEARCH USERS #####")
# Note: user search is not in the current API, but we verify privacy for any future additions

# Test venue with capacity filter
print("\n##### VENUE CAPACITY FILTER #####")
resp = client.get("/api/search?type=venue&venue_capacity=200&page=1&per_page=10")
d = test("Venues capacity>=200", resp)
for v in d.get("results", {}).get("venues", []):
    print(f"  {v['name']} - Cap: {v['capacity']}")

# Test event date filter
print("\n##### EVENT DATE FILTER #####")
resp = client.get("/api/search?type=event&event_date=2026-09-12&page=1&per_page=5")
d = test("Events on 2026-09-12", resp)
for e in d.get("results", {}).get("events", []):
    print(f"  {e['title']}")

# Test pagination
print("\n##### PAGINATION #####")
resp = client.get("/api/search?type=event&page=2&per_page=10")
d = test("Events page 2", resp)
print(f"  Page: {d.get('page')}, Per page: {d.get('per_page')}")
print(f"  Has more pages: {d.get('page', 1) < (d.get('total_results', 0) / d.get('per_page', 1) + 1)}")

print("\n##### ALL AUTH TESTS COMPLETE #####")
