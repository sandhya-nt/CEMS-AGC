"""Verify app startup."""
import os
os.environ['SECRET_KEY'] = 'test-secret'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

from app import app

print("App imported successfully")
print("Assistant routes:")
for rule in app.url_map.iter_rules():
    if "assistant" in rule.rule:
        print("  {} -> {}".format(rule.rule, rule.endpoint))

print("\n=== APP VERIFICATION PASSED ===")
