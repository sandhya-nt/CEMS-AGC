import os
os.environ['FLASK_DEBUG'] = '0'
os.environ['FLASK_ENV'] = 'development'

# Get original model columns from git
import subprocess

original_app = subprocess.check_output(
    ['git', 'show', 'HEAD:app.py'], 
    cwd='C:\\Users\\shqqq\\Downloads\\CEMS_AGC_GitHub_Ready',
    text=True,
    encoding='utf-8',
    errors='replace'
)

# Parse original table columns
import re

def parse_columns(source_code):
    """Parse db.Column definitions from class definitions in source code."""
    tables = {}
    lines = source_code.split('\n')
    current_class = None
    current_table = None
    
    for line in lines:
        # Match class definitions
        class_match = re.match(r'^class\s+(\w+)\(.*db\.Model.*\):', line)
        if class_match:
            class_name = class_match.group(1)
            current_class = class_name
            # Convert CamelCase to snake_case for table name
            table_name = re.sub(r'(?<!^)(?=[A-Z])', '_', class_name).lower()
            table_name = table_name.rstrip('_')
            # Special cases
            if class_name == 'User':
                table_name = 'user'
            elif class_name == 'Event':
                table_name = 'event'
            elif class_name == 'Registration':
                table_name = 'registration'
            current_table = table_name
            tables[current_table] = set()
            continue
        
        # Also check for __tablename__ override
        tn_match = re.match(r'^\s+__tablename__\s*=\s*"(\w+)"', line)
        if tn_match and current_class:
            current_table = tn_match.group(1)
            if current_table not in tables:
                tables[current_table] = set()
            continue
        
        # Match column definitions
        if current_class and 'db.Column' in line:
            col_match = re.match(r'^\s+(\w+)\s*=\s*db\.Column', line)
            if col_match:
                col_name = col_match.group(1)
                tables[current_table].add(col_name)
    
    return tables

original_cols = parse_columns(original_app)

# Get current model columns
from app import app, db, ensure_legacy_schema_compatibility
import inspect

with app.app_context():
    current_cols = {}
    for table_name, table in db.metadata.tables.items():
        current_cols[table_name] = set(table.columns.keys())

    # The compat dict from current app.py
    source = inspect.getsource(ensure_legacy_schema_compatibility)
    # Extract additions dict
    compat_tables = set()
    compat_cols = {}
    for match in re.finditer(r'"(\w+)":\s*\{([^}]+)\}', source):
        table_name = match.group(1)
        cols_str = match.group(2)
        cols = set(re.findall(r'"(\w+)"', cols_str))
        compat_tables.add(table_name)
        compat_cols[table_name] = cols

    print("=== NEW columns added to existing tables (in current but NOT in original) ===")
    print("=== that are NOT in the compat dict ===\n")

    all_tables_to_check = set(original_cols.keys()) & set(current_cols.keys())

    for table_name in sorted(all_tables_to_check):
        original = original_cols.get(table_name, set())
        current = current_cols.get(table_name, set())
        compat = compat_cols.get(table_name, set())
        
        new_cols = current - original  # Columns that are new (added by our changes)
        missing_from_compat = new_cols - compat  # New columns not in compat dict
        
        if missing_from_compat:
            print(f"Table '{table_name}': NEW columns NOT in compat dict:")
            for col in sorted(missing_from_compat):
                print(f"  MISSING: {col}")
            print()

    print("\n=== Done ===")
