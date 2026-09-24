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
    if data.get("empty_messages"):
        print(f"  Empty msgs: {data['empty_messages']}")
    return data

# Test 1: Autocomplete
print("\n##### AUTOCOMPLETE #####")
d = test("Autocomplete q=AGC", client.get("/api/search/autocomplete?q=AGC"))
for s in d.get("suggestions", [])[:5]:
    print(f"  {s['type']}: {s['title']}")

# Test 2: Search all with query
print("\n##### SEARCH ALL #####")
d = test("Search q=Test", client.get("/api/search?q=Test&page=1&per_page=5"))

# Test 3: Event search
print("\n##### EVENT SEARCH #####")
d = test("Events page 1", client.get("/api/search?type=event&page=1&per_page=5"))
for e in d.get("results", {}).get("events", [])[:3]:
    print(f"  {e['title']} - {e['category']} - {e['venue']} - {e['status']}")

# Test 4: Event search with filters
print("\n##### EVENT SEARCH WITH FILTERS #####")
d = test("Events category=Technical", client.get("/api/search?type=event&event_category=Technical&page=1&per_page=5"))
print(f"  Found {d['totals']['events']} technical events")

# Test 5: Venue search
print("\n##### VENUE SEARCH #####")
d = test("Venues page 1", client.get("/api/search?type=venue&page=1&per_page=5"))
for v in d.get("results", {}).get("venues", [])[:3]:
    print(f"  {v['name']} - {v['building']} - {v['venue_type']} - Cap: {v['capacity']}")

# Test 6: Venue search with building filter
print("\n##### VENUE FILTER #####")
d = test("Venues building=Main", client.get("/api/search?type=venue&venue_building=Main&page=1&per_page=5"))
for v in d.get("results", {}).get("venues", [])[:3]:
    print(f"  {v['name']}")

# Test 7: Notice search
print("\n##### NOTICE SEARCH #####")
d = test("Notices page 1", client.get("/api/search?type=notice&page=1&per_page=5"))
for n in d.get("results", {}).get("notices", [])[:3]:
    print(f"  {n['title']} - {n['category']}")

# Test 8: Certificate search (no auth)
print("\n##### CERTIFICATE SEARCH (no auth) #####")
d = test("Certificates no auth", client.get("/api/search?type=certificate&page=1&per_page=5"))
print(f"  Result: {d['totals']['certificates']} certificates found")

# Test 9: Resource search
print("\n##### RESOURCE SEARCH #####")
d = test("Resources page 1", client.get("/api/search?type=resource&page=1&per_page=5"))
print(f"  Result: {d['totals']['resources']} resources found")

# Test 10: Empty results
print("\n##### EMPTY STATE #####")
d = test("Search q=zzznomatchzzz", client.get("/api/search?q=zzznomatchzzz&page=1&per_page=5"))
print(f"  Empty msg events: {d['empty_messages'].get('events')}")

print("\n##### ALL TESTS COMPLETE #####")
