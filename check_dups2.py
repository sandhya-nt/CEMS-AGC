import os
os.environ['FLASK_DEBUG'] = '0'
os.environ['FLASK_ENV'] = 'development'

import re
from collections import Counter

# Check for duplicate function definitions in services.py
for filepath in ['cems/services.py', 'cems/domain.py', 'app.py']:
    fname = filepath.split('/')[-1]
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    funcs = []
    for i, line in enumerate(lines):
        m = re.match(r'\s*def (\w+)\s*\(', line)
        if m:
            funcs.append((m.group(1), i+1))
    
    counts = Counter(f[0] for f in funcs)
    dups = {k: v for k, v in counts.items() if v > 1}
    if dups:
        print(f"\n=== {fname}: DUPLICATE FUNCTIONS ===")
        for name, count in dups.items():
            locations = [f for f in funcs if f[0] == name]
            print(f"  {name}: {count} times at lines {[loc[1] for loc in locations]}")

# Check for duplicate class definitions
print("\n=== Checking class definitions ===")
for filepath in ['cems/services.py', 'cems/domain.py', 'app.py']:
    fname = filepath.split('/')[-1]
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    classes = []
    for i, line in enumerate(lines):
        m = re.match(r'class (\w+)\s*[(\[]', line)
        if m:
            classes.append((m.group(1), i+1))
    
    counts = Counter(c[0] for c in classes)
    dups = {k: v for k, v in counts.items() if v > 1}
    if dups:
        print(f"  {fname}: DUP CLASSES: {dups}")
