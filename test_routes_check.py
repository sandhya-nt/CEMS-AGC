import os, sys
os.environ['SECRET_KEY'] = 'test-secret'
os.environ['DATABASE_URL'] = 'sqlite:///test_routes3.db'
sys.path.insert(0, '.')
from app import app as flask_app, db
with flask_app.app_context():
    db.create_all()
    all_endpoints = set(r.endpoint for r in flask_app.url_map.iter_rules())
    for name in ['volunteer_opportunities', 'student_events', 'agc_notices', 'past_events',
                 'festival_calendar', 'checkin', 'organizer_support', 'api_search_autocomplete',
                 'organizer_participants', 'kiosk', 'teacher_incidents', 'teacher_certificates',
                 'teacher_notifications', 'teacher_volunteers', 'teacher_tasks']:
        print(f'  {name}: {"EXISTS" if name in all_endpoints else "MISSING"}')
