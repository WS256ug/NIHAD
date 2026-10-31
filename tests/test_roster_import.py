import csv
import hashlib
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.admin.models import LogEntry
from django.core.exceptions import PermissionDenied
from django.core.management import call_command, CommandError

from apps.students.models import Student, Guardian, Enrollment, StudentNumber
from apps.students.management.commands.import_student_roster import HEADERS, read_roster
from tests.test_students import StudentTestCase


class RosterImportTests(StudentTestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'roster.csv'
        self.rows = [dict(zip(HEADERS, ['1', 'Alex Sample One', 'M', 'Muslim',
            '700000001 / 0700000002', 'Jane Example / Paul Example', 'Mother', 'Active', '1/2/2026 11:15']))]
        self.write()

    def write(self):
        with self.path.open('w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerows(self.rows)

    def run_import(self, **changes):
        options = dict(file=str(self.path), actor=self.actor.username, academic_year=self.year.name,
            section_name=self.primary.name, class_name=self.academic_class.name, stream_name=self.stream.name,
            temporary_birth_date='2026-01-01', expected_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(), stdout=StringIO())
        options.update(changes)
        call_command('import_student_roster', **options)
        return options['stdout'].getvalue()

    def test_preview_rolls_back_students_contacts_enrollments_counter_and_audit(self):
        counts = [model.objects.count() for model in (Student, Guardian, Enrollment, LogEntry)]
        number = StudentNumber.objects.get(school=self.school).last_value
        self.assertIn('PREVIEW PASSED', self.run_import())
        self.assertEqual(counts, [model.objects.count() for model in (Student, Guardian, Enrollment, LogEntry)])
        self.assertEqual(StudentNumber.objects.get(school=self.school).last_value, number)

    def test_apply_preserves_authorized_values_and_rejects_repeat(self):
        self.run_import(apply=True)
        student = Student.objects.get(first_name='Alex')
        self.assertEqual(student.full_name, 'Alex Sample One')
        self.assertEqual(student.date_of_birth.isoformat(), '2026-01-01')
        self.assertEqual(student.religion, 'Moslem')
        self.assertIsNone(student.portal_user_id)
        self.assertEqual(student.guardian_links.count(), 2)
        self.assertEqual(set(student.guardian_links.values_list('relationship', flat=True)), {'Mother'})
        self.assertEqual(student.guardian_links.filter(is_primary=True).count(), 1)
        self.assertEqual(student.guardian_links.first().guardian.phone, '0700000001 / 0700000002')
        self.assertEqual(student.enrollments.get().programme, 'main')
        self.assertTrue(LogEntry.objects.filter(change_message__contains='TEMPORARY birth date').exists())
        with self.assertRaisesMessage(CommandError, 'Possible existing students'):
            self.run_import(apply=True)

    def test_invalid_later_row_rolls_back_entire_batch(self):
        self.rows.append({**self.rows[0], 'No': '2', 'Student Name': 'Other Learner', 'admission dates': '1/1/2025'})
        self.write()
        count = Student.objects.count()
        with self.assertRaises(CommandError):
            self.run_import(apply=True)
        self.assertEqual(Student.objects.count(), count)

    def test_file_change_wrong_scope_and_unauthorized_actor_rejected(self):
        with self.assertRaises(CommandError):
            self.run_import(apply=True, expected_sha256='stale')
        with self.assertRaises(CommandError):
            self.run_import(stream_name='Missing')
        from apps.accounts.models import User
        with self.assertRaises(PermissionDenied):
            self.run_import(actor=self.users[User.Role.TEACHER].username)

    def test_existing_name_order_and_in_file_duplicate_are_blocked(self):
        self.rows[0]['Student Name'] = 'WASSWA MARY'
        self.write()
        with self.assertRaisesMessage(CommandError, 'Possible existing students'):
            self.run_import()
        self.rows.append({**self.rows[0], 'No': '2', 'Student Name': 'MARY WASSWA'})
        self.write()
        with self.assertRaisesMessage(CommandError, 'Repeated student name'):
            self.run_import()

    def test_siblings_reuse_exact_contacts_and_single_names_are_not_invented(self):
        self.rows[0]['Parent / Guardian Name'] = 'Olivia'
        self.rows.append({**self.rows[0], 'No': '2', 'Student Name': 'Another Sample Learner'})
        self.write()
        self.run_import(apply=True)
        guardian = Guardian.objects.get(first_name='Olivia')
        self.assertEqual(guardian.last_name, '(not supplied)')
        self.assertEqual(guardian.student_links.count(), 2)

    def test_nonstandard_numeric_phone_preserved_with_warning(self):
        self.rows[0]['Phone Contact'] = '7716669381'
        self.write()
        rows, _ = read_roster(self.path)
        self.assertEqual(rows[0]['phone'], '7716669381')
        self.assertTrue(any('Phone format' in warning for warning in rows[0]['warnings']))

    def middle_file(self):
        headers = ['Stream', 'Class'] + ['RelationShip' if h == 'Relationship' else h for h in HEADERS if h != 'admission dates']
        data = []
        for stream, name in [('East', 'First Middle Learner'), ('West', 'Second Middle Learner')]:
            row = {**self.rows[0], 'No': '1', 'Student Name': name, 'Stream': stream, 'Class': self.academic_class.name}
            row['RelationShip'] = row.pop('Relationship')
            row.pop('admission dates')
            data.append(row)
        with self.path.open('w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()
            writer.writerows(data)

    def test_multi_stream_import_with_repeated_row_numbers_and_default_date(self):
        from apps.schools.models import Stream
        Stream.objects.create(academic_class=self.academic_class, name='West')
        self.middle_file()
        self.run_import(apply=True, stream_name=None, admission_date='2026-01-02')
        self.assertEqual(Enrollment.objects.get(student__first_name='First').stream.name, 'East')
        self.assertEqual(Enrollment.objects.get(student__first_name='Second').stream.name, 'West')

    def test_missing_stream_or_conflicting_override_does_not_import_any_rows(self):
        self.middle_file()
        before = Student.objects.count()
        with self.assertRaisesMessage(CommandError, 'stream West'):
            self.run_import(apply=True, stream_name=None, admission_date='2026-01-02')
        with self.assertRaisesMessage(CommandError, 'stream does not match'):
            self.run_import(apply=True, admission_date='2026-01-02')
        self.assertEqual(Student.objects.count(), before)

    def test_missing_dates_require_explicit_default(self):
        self.middle_file()
        with self.assertRaisesMessage(CommandError, 'admission-date'):
            self.run_import(stream_name=None)
