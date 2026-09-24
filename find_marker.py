import sys
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

partial = 'return render_template("student/register_event.html"'
if partial in content:
    pos = content.find(partial)
    snippet = content[pos:pos+200]
    print("Found at position:", pos)
    print(repr(snippet))
else:
    print("NOT FOUND")
