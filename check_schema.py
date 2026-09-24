import os
os.environ['FLASK_DEBUG'] = '0'
os.environ['FLASK_ENV'] = 'development'

from app import app, db, ensure_legacy_schema_compatibility
from sqlalchemy import inspect as sa_inspect, text
from sqlalchemy.orm import declarative_base

# The additions dict from ensure_legacy_schema_compatibility
additions = {
    "user": {"student_id", "employee_id", "profile_image", "settings_json", "last_login_at", "remember_token"},
    "event": {
        "registration_start", "published_at", "updated_at", "cancellation_reason", "results",
        "documents_json", "custom_questions_json", "contact_person", "contact_email",
        "contact_phone", "venue_id", "cancellation_requested_at", "cancellation_requested_by",
        "cancelled_at", "cancelled_by", "cancellation_admin_notes", "reschedule_requested_at",
        "reschedule_requested_by", "proposed_date", "proposed_start_time", "proposed_end_time",
        "proposed_venue", "proposed_capacity", "proposed_venue_id", "reschedule_reason",
        "reschedule_admin_notes", "completed_at", "completed_by", "completion_notes",
        "feedback_enabled", "feedback_eligibility", "feedback_allow_updates", "feedback_deadline_days",
    },
    "venue": {"building", "floor", "room_number", "location_description", "venue_type", "facilities",
              "status", "image", "map_coordinates", "created_at", "updated_at"},
    "registration": {"terms_accepted", "cancellation_reason", "cancelled_at"},
    "feedback": {"organization_rating", "venue_rating", "speaker_rating",
                 "registration_experience_rating", "comment", "is_anonymous", "theme"},
    "notification": {"category", "action_url", "expires_at"},
    "notice": {"attachment_name", "expiry_date", "updated_at"},
    "event_gallery": {"caption"},
    "event_waitlist": {"status"},
    "attendance_record": {"status", "scanned_by"},
    "past_event": {"archived_by", "highlights", "results", "documents_json"},
    "faculty_profile": {"employee_id", "bio"},
    "student_profile": {"batch"},
    "volunteer_assignment": {"student_id", "role_id", "application_id", "assigned_by",
                             "notes", "hours_worked", "completed_at", "created_at", "updated_at"},
    "event_custom_field": {"placeholder", "help_text", "validation_json", "is_active", "updated_at"},
}

# Collect all model columns for each table
from app import db
metadata = db.metadata

print("=== Checking model columns vs ensure_legacy_schema_compatibility additions ===\n")

# Get all table names from the model
model_tables = set(metadata.tables.keys())
compat_tables = set(additions.keys())

# Tables in model but not in compat dict (these need creation handling)
# Actually db.create_all handles new tables, so only check columns for existing tables

for table_name in sorted(model_tables):
    if table_name not in additions:
        continue
    table = metadata.tables[table_name]
    model_cols = set(table.columns.keys())
    compat_cols = additions.get(table_name, set())
    missing = model_cols - compat_cols
    if missing:
        print(f"Table '{table_name}': {len(missing)} MISSING from compat dict:")
        for col in sorted(missing):
            col_type = table.columns[col].type
            print(f"  - {col} ({col_type})")

# Also check: tables in model but not in additions dict at all
new_tables = model_tables - compat_tables
new_tables = new_tables - {"sqlite_sequence", "alembic_version"}  # Skip system tables
if new_tables:
    print(f"\n=== Tables in model but NOT in compat dict (will be created by create_all) ===")
    for t in sorted(new_tables):
        print(f"  {t}")

# Also check for tables in compat dict but not in model
extra_tables = compat_tables - model_tables
if extra_tables:
    print(f"\n=== Tables in compat dict but NOT in model ===")
    for t in sorted(extra_tables):
        print(f"  {t}")
