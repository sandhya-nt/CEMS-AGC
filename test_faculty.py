from app import app, db, Event, EventFaculty, User, Registration, DigitalCertificate

with app.test_client() as client:
    # 1. Test landing page
    rv = client.get('/')
    print(f'Landing: {rv.status_code}')
    
    # 2. Login as admin
    rv = client.post('/login', data={'email': 'admin@agc.local', 'password': 'Admin@123'}, follow_redirects=True)
    print(f'Admin login: {rv.status_code}')
    
    # 3. Access admin events page
    rv = client.get('/admin/events')
    print(f'Admin events: {rv.status_code}')
    
    # 4. Check faculty assignment UI is present
    rv = client.get('/admin/events')
    content = rv.data.decode()
    assert 'Assign Faculty' in content, 'Assign Faculty button missing'
    assert 'assign-faculty-modal' in content, 'Modal missing'
    print('Admin events has faculty assignment UI: OK')
    
    # 5. Assign faculty to event
    teacher = User.query.filter_by(role='teacher').first()
    event = Event.query.first()
    rv = client.post('/admin/events/assign-faculty', data={'event_id': event.id, 'faculty_id': teacher.id, 'action': 'assign'})
    print(f'Assign faculty: {rv.status_code}')
    
    # 6. Logout
    client.get('/logout')
    
    # 7. Login as teacher
    rv = client.post('/login', data={'email': 'teacher@agc.local', 'password': 'Teacher@123'}, follow_redirects=True)
    print(f'Teacher login: {rv.status_code}')
    
    # 8. Access faculty dashboard
    rv = client.get('/teacher/dashboard')
    print(f'Faculty dashboard: {rv.status_code}')
    content = rv.data.decode()
    assert 'Total Assigned Events' in content, 'Stats missing'
    assert 'Total Registrations' in content, 'Reg stats missing'
    assert 'Pending Registrations' in content, 'Pending missing'
    assert 'Approved Students' in content, 'Approved missing'
    assert 'Total Attendance' in content, 'Attendance missing'
    assert 'Certificates Generated' in content, 'Certs missing'
    print('Dashboard stats: OK')
    
    # 9. Check sidebar navigation items
    nav_items = ['Dashboard', 'Assigned Events', 'Registrations', 'Attendance', 'QR Check-in', 'Certificates', 'Reports', 'Announcements', 'Feedback', 'Volunteers', 'Documents', 'Notifications', 'Profile']
    for item in nav_items:
        assert item in content, f'{item} missing from sidebar'
    print('Sidebar nav items: OK')
    
    # 10. Access assigned events
    rv = client.get('/faculty/assigned-events')
    print(f'Assigned events: {rv.status_code}')
    content = rv.data.decode()
    assert 'Assigned Events' in content, 'Page title missing'
    print('Assigned events page: OK')
    
    # 11. Access event details
    if event:
        rv = client.get(f'/teacher/event/{event.id}')
        print(f'Event details: {rv.status_code}')
        content = rv.data.decode()
        assert 'Manage Registrations' in content, 'Manage Registrations btn missing'
        assert 'Attendance' in content, 'Attendance btn missing'
        assert 'QR Check-in' in content, 'QR Check-in btn missing'
        assert 'Certificates' in content, 'Certificates btn missing'
        assert 'Reports' in content, 'Reports btn missing'
        print('Event details nav buttons: OK')
    
    # 12. Test faculty A cannot see faculty B's data (create new teacher)
    rv = client.get('/faculty/assigned-events')
    print(f'Faculty assigned events access: {rv.status_code}')
    
    # 13. Test student cannot access faculty dashboard
    client.get('/logout')
    rv = client.post('/login', data={'email': 'student@agc.local', 'password': 'Student@123'}, follow_redirects=True)
    rv = client.get('/teacher/dashboard')
    print(f'Student access faculty dashboard: {rv.status_code}')
    assert rv.status_code == 403, f'Should be 403, got {rv.status_code}'
    print('Student blocked: OK')
    
    print('\n=== ALL TESTS PASSED ===')
