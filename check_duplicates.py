import re
from collections import Counter

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
routes = []
for i, line in enumerate(lines):
    m = re.match(r'@app\.route\(([^,]+)', line.strip())
    if m:
        route = m.group(1).strip().strip('\"').strip("'")
        # find next def
        for j in range(i+1, min(i+10, len(lines))):
            dm = re.match(r'def (\w+)', lines[j].strip())
            if dm:
                routes.append((route, dm.group(1)))
                break

route_counts = Counter(r[0] for r in routes)
print('=== DUPLICATE ROUTES ===')
for route, count in sorted(route_counts.items()):
    if count > 1:
        print(f'  {route}: {count} times')

func_counts = Counter(r[1] for r in routes)
print('=== DUPLICATE FUNCTION NAMES ===')
for func, count in sorted(func_counts.items()):
    if count > 1:
        matches = [r[0] for r in routes if r[1] == func]
        print(f'  {func}: {count} times -> {matches}')

# Also check duplicate def without routes
all_defs = []
for line in lines:
    m = re.match(r'def (\w+)', line.strip())
    if m:
        all_defs.append((m.group(1), line.strip()))

def_counts = Counter(d[0] for d in all_defs)
print('\n=== ALL DUPLICATE FUNCTION DEFS ===')
for func, count in sorted(def_counts.items()):
    if count > 1:
        print(f'  {func}: {count} times')
