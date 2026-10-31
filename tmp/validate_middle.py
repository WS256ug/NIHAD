import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
import django
django.setup()
from io import StringIO
from django.test.utils import setup_databases, teardown_databases, setup_test_environment
from django.core.management import call_command
from apps.accounts.models import User
from apps.schools.models import School, Section, AcademicYear, AcademicClass, Stream
from apps.students.models import Student
setup_test_environment()
config=setup_databases(verbosity=0,interactive=False)
try:
 school=School.objects.create(name='Isolated import validation')
 section=Section.objects.create(school=school,name='Nursery')
 classroom=AcademicClass.objects.create(section=section,name='Middle')
 Stream.objects.create(academic_class=classroom,name='Daises')
 Stream.objects.create(academic_class=classroom,name='Lavenders')
 AcademicYear.objects.create(school=school,name='2026/27',start_date='2026-07-01',end_date='2027-06-30')
 User.objects.create(username='import-validation',role='super_admin',is_superuser=True,is_staff=True)
 out=StringIO()
 call_command('import_student_roster',file=r'E:/MOVIES 2026/middle_class_roster.csv',actor='import-validation',academic_year='2026/27',section_name='Nursery',class_name='Middle',admission_date='2026-10-30',temporary_birth_date='2026-01-01',stdout=out)
 print(out.getvalue().splitlines()[-1])
 print('Student count after preview:',Student.objects.count())
finally:
 teardown_databases(config,verbosity=0)

