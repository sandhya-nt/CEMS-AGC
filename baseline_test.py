import os, sys, time, urllib.request, urllib.parse, json, subprocess, threading

BASE = "http://127.0.0.1:5000"

def get(path, **kw):
    url = BASE + path
    req = urllib.request.Request(url, headers=kw.get("headers", {}))
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')
    except Exception as e:
        return None, str(e)

def post(path, data=None, headers=None, method="POST"):
    url = BASE + path
    h = {"Content-Type": "application/x-www-form-urlencoded"}
    if headers:
        h.update(headers)
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')
    except Exception as e:
        return None, str(e)

def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    return cond

print("=== BASELINE TEST ===")
# public pages
for p in ["/", "/events", "/login", "/register", "/notices", "/past-events", "/search"]:
    s, b = get(p)
    check(f"GET {p}", s == 200, f"got {s}")