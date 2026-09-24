import sys
sys.path.insert(0, '.')
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('templates'))
template = env.get_template('auth/faculty_register.html')

class MockUser:
    is_authenticated = False

html = template.render(
    csrf_token='test_token',
    errors={},
    request=type('MockRequest', (), {'form': {}})(),
    url_for=lambda name, **kwargs: '/mock/' + name,
    current_user=MockUser(),
    college_short='AGC',
    college_name='Amritsar Group of Colleges',
    current_year=2026,
)

print('Template rendered successfully')

checks = [
    ('No roll_no field', 'reg-roll_no' not in html and 'name="roll_no"' not in html),
    ('No student_id field', 'reg-student_id' not in html and 'name="student_id"' not in html),
    ('No course field', 'reg-course' not in html),
    ('No semester field', 'reg-semester' not in html),
    ('No section field', 'reg-section' not in html),
    ('No batch field', 'reg-batch' not in html),
    ('Has Full Name', 'Full Name' in html),
    ('Has Official Email', 'Official Email' in html),
    ('Has Phone Number', 'Phone Number' in html),
    ('Has Profile Photo', 'Profile Photo' in html),
    ('Has Official Faculty ID', 'Official Faculty ID' in html),
    ('Has Department', 'Department' in html),
    ('Has Designation / Role', 'Designation / Role' in html),
    ('Has Password', 'Password' in html),
    ('Has Confirm Password', 'Confirm Password' in html),
    ('Has heading', 'Create your Faculty Account' in html),
    ('Has supporting text', 'Access faculty-related campus activities' in html),
    ('Has section 1', 'Personal Information' in html),
    ('Has section 2', 'Faculty Identification' in html),
    ('Has section 3', 'Professional Information' in html),
    ('Has section 4', 'Account Security' in html),
    ('No faculty_role select', 'faculty_role' not in html),
    ('No academic_session select', 'academic_session' not in html),
]

all_pass = True
for label, result in checks:
    status = 'PASS' if result else 'FAIL'
    if not result:
        all_pass = False
    print(f'{status}: {label}')

print()
print('ALL CHECKS PASSED' if all_pass else 'SOME CHECKS FAILED')
