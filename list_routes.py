import re
with open('app.py','r',encoding='utf-8') as f:
    src=f.read()
routes=re.findall(r'@app\.route\("([^"]+)"', src)
print('TOTAL ROUTES:', len(routes))
for r in routes:
    print(r)