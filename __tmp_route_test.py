import sys
sys.path.insert(0, ".")
from app import app

client = app.test_client()

routes_to_check = [
    ("/events", "GET"),
    ("/events/1", "GET"),
    ("/teacher/assigned-events", "GET"),
    ("/student/events", "GET"),
    ("/organizer/festival-calendar", "GET"),
    ("/organizer/checkin/scan", "GET"),
    ("/organizer/dashboard", "GET"),
    ("/organizer/events/1/registrations", "GET"),
    ("/organizer/events/1/registrations/export", "GET"),
    ("/teacher/volunteers", "GET"),
    ("/login", "GET"),
    ("/organizer/volunteer-management", "GET"),
    ("/organizer/events/1/participants", "GET"),
]

for path, method in routes_to_check:
    resp = client.open(path, method=method)
    print(f"{method} {path} -> {resp.status_code}")
    if resp.status_code >= 500:
        body = resp.get_data(as_text=True)
        print("  ERROR:", body[:500])
