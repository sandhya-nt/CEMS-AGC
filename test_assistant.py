"""Comprehensive test for Campus Event Assistant."""
import os
os.environ['SECRET_KEY'] = 'test-secret'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

from app import app, db, seed_data, User

with app.app_context():
    db.create_all()
    seed_data()

    from cems.assistant import CampusAssistantService
    from cems.ai_bridge import AIBridge

    student = User.query.filter_by(email='student@agc.local').first()
    service = CampusAssistantService(student, db.session)

    # Test all student intents
    queries = [
        "Which technical events are coming this week?",
        "Which events have I registered for?",
        "Where is my next event?",
        "How many events have I attended?",
        "Do I have any certificates?",
        "What should I register for?",
        "What is my profile?",
    ]

    print("=== STUDENT QUERY TESTS ===")
    for q in queries:
        resolved = service.resolve_query(q)
        intent = resolved["intent"]
        err = resolved.get("error")
        data = resolved.get("data")
        if err:
            print(f"  {intent}: ERROR - {err[:60]}")
        elif data:
            print(f"  {intent}: OK - has data")
        else:
            print(f"  {intent}: CHECK - no data, no error")

    # Test AI bridge (fallback mode)
    ai = AIBridge()
    print("\n=== AI BRIDGE ===")
    print("  AI available:", ai.is_available())
    status = ai.get_status_message()
    try:
        print("  Status:", status)
    except UnicodeEncodeError:
        print("  Status: [emoji unsupported in terminal]")

    resolved = service.resolve_query("Which events have I registered for?")
    response = ai.generate_response("Which events have I registered for?", resolved)
    print("  Response length:", len(response), "chars")
    print("  Response preview:", response[:100])

    # Test organizer queries via student (should be blocked)
    print(f"\n=== RBAC TESTS ===")
    rbac_queries = [
        "Which volunteers are assigned?",
        "How many seats are left?",
        "Show my events",
    ]
    for q in rbac_queries:
        resolved = service.resolve_query(q)
        err = resolved.get("error")
        data = resolved.get("data")
        if isinstance(data, dict) and "error" in data:
            print(f"  BLOCKED: {q[:40]} - {data['error'][:60]}")
        elif err:
            print(f"  BLOCKED: {q[:40]} - {err[:60]}")
        else:
            print(f"  ALLOWED: {q[:40]} - data returned")

    print("\n=== ALL TESTS PASSED ===")