"""Preview-first, atomic registration of a reviewed class roster."""
import csv
import hashlib
import io
import re
from datetime import date, datetime
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.schools.models import AcademicClass, AcademicYear, Stream
from apps.schools.services import lock_school, write_record
from apps.students.forms import StudentRegistrationForm, EnrollmentForm
from apps.students.models import Student, Guardian
from apps.students.services import require_manager, save_student, enroll_student, add_guardian_contact


HEADERS = ('No', 'Student Name', 'Gender', 'Religion', 'Phone Contact',
           'Parent / Guardian Name', 'Relationship', 'Status', 'admission dates')


def name_key(value):
    # Flag exact token matches even when a surname was entered first elsewhere.
    return tuple(sorted(value.casefold().split()))


def name_parts(value, guardian=False):
    parts = value.split()
    if not parts or (len(parts) < 2 and not guardian):
        raise ValueError('Student names need at least two components; guardian name cannot be empty.')
    if guardian:
        return parts[0], ' '.join(parts[1:]) or '(not supplied)'
    return parts[0], ' '.join(parts[1:-1]), parts[-1]


def phone_contacts(value):
    contacts, warnings = [], []
    for part in value.split('/'):
        number = re.sub(r'[\s()-]', '', part)
        if re.fullmatch(r'7\d{8}', number):
            number = '0' + number
        if not re.fullmatch(r'0\d{9}|\+256\d{9}|256\d{9}', number):
            warnings.append('Phone format needs review; original digits preserved.')
        if not number or not re.fullmatch(r'\+?\d+', number):
            raise ValueError('Phone contact must contain digits, with / between multiple contacts.')
        contacts.append(number)
    return ' / '.join(contacts), warnings


def read_roster(path, admission_date=None):
    raw = Path(path).read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    if reader.fieldnames:
        reader.fieldnames = [('Relationship' if name.strip().casefold() == 'relationship' else name.strip()) for name in reader.fieldnames]
    required = set(HEADERS) - {'admission dates'}
    if (not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames)
            or not required <= set(reader.fieldnames)
            or set(reader.fieldnames) - set(HEADERS) - {'Stream', 'Class'}):
        raise ValueError('CSV requires the roster columns, with optional Class, Stream and admission dates.')
    rows, keys, numbers = [], set(), set()
    for line, source in enumerate(reader, 2):
        if None in source or any(value is None for value in source.values()):
            raise ValueError(f'CSV line {line}: incorrect number of columns.')
        row = {key: value.strip() for key, value in source.items()}
        if not any(row.values()):
            continue
        try:
            if row['Status'].casefold() != 'active':
                raise ValueError('Only explicitly Active rows can be registered.')
            key = name_key(row['Student Name'])
            source_key = (row.get('Stream', '').casefold(), row['No'])
            if key in keys or not row['No'] or source_key in numbers:
                raise ValueError('Repeated student name or source row number; review before importing.')
            keys.add(key)
            numbers.add(source_key)
            first, middle, last = name_parts(row['Student Name'])
            gender = {'f': 'female', 'm': 'male', 'female': 'female', 'male': 'male'}.get(row['Gender'].casefold())
            religion = {'muslim': 'Moslem', 'moslem': 'Moslem', 'islam': 'Moslem', 'christian': 'Christian', 'other': 'Other'}.get(row['Religion'].casefold())
            if not gender or not religion or not row['Relationship']:
                raise ValueError('Gender, religion and relationship must be supplied and recognised.')
            admission = None
            for fmt in ('%m/%d/%Y %H:%M', '%m/%d/%Y', '%Y-%m-%d'):
                try:
                    admission = datetime.strptime(row.get('admission dates') or admission_date or '', fmt).date()
                    break
                except ValueError:
                    pass
            if not admission:
                raise ValueError('Supply admission dates in the CSV or --admission-date YYYY-MM-DD.')
            phone, warnings = phone_contacts(row['Phone Contact'])
            guardians = [name_parts(value.strip(), guardian=True) for value in row['Parent / Guardian Name'].split('/')]
            if len(guardians) > 1:
                warnings.append('Same supplied relationship and shared contact list retained for each guardian; phone ownership not inferred.')
            if any(last_name == '(not supplied)' for _, last_name in guardians):
                warnings.append('Missing guardian surname explicitly recorded as (not supplied).')
            source_label = f'{row["Stream"]}/{row["No"]}' if row.get('Stream') else row['No']
            rows.append(dict(source=source_label, name=row['Student Name'], first_name=first,
                             middle_name=middle, last_name=last, gender=gender, religion=religion,
                             admission_date=admission, phone=phone, guardians=guardians,
                             relationship=row['Relationship'], warnings=warnings,
                             stream=row.get('Stream', ''), classroom=row.get('Class', '')))
        except ValueError as exc:
            raise ValueError(f'CSV line {line}, source row {row["No"]}: {exc}') from exc
    if not rows:
        raise ValueError('The roster is empty.')
    return rows, hashlib.sha256(raw).hexdigest()


class Command(BaseCommand):
    help = 'Preview or apply a reviewed roster using normal registration and enrollment validation.'

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True)
        parser.add_argument('--actor', required=True, help='Active administrator username')
        parser.add_argument('--academic-year', required=True)
        parser.add_argument('--section-name', required=True)
        parser.add_argument('--class-name', required=True)
        parser.add_argument('--stream-name', help='Required when CSV has no Stream column; must match if supplied in both.')
        parser.add_argument('--admission-date', help='Explicit default YYYY-MM-DD for missing CSV admission dates.')
        parser.add_argument('--temporary-birth-date', required=True, help='Explicitly authorised temporary birth date, YYYY-MM-DD; recorded in audit history.')
        parser.add_argument('--enrollment-date', help='YYYY-MM-DD; defaults to each supplied admission date.')
        parser.add_argument('--expected-sha256', help='Required with --apply; use the hash printed by the successful preview.')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            rows, digest = read_roster(options['file'], options.get('admission_date'))
            birth = date.fromisoformat(options['temporary_birth_date'])
            enrollment_date = date.fromisoformat(options['enrollment_date']) if options.get('enrollment_date') else None
            if options['apply'] and options.get('expected_sha256') != digest:
                raise CommandError('File hash does not match --expected-sha256. Run a new preview first.')
            self.import_rows(rows, digest, birth, enrollment_date, options)
        except (OSError, UnicodeError, ValueError, ValidationError, csv.Error) as exc:
            raise CommandError(str(exc)) from exc

    @transaction.atomic
    def import_rows(self, rows, digest, birth, enrollment_date, options):
        actor = User.objects.filter(username=options['actor'], is_active=True).first()
        if not actor:
            raise CommandError('Choose an active School Admin or Super Admin.')
        require_manager(actor)
        school = lock_school()

        def one(queryset, label):
            records = list(queryset[:2])
            if len(records) != 1:
                raise CommandError(f'Expected exactly one active {label}; found {len(records)}. Check school configuration and command spelling.')
            return records[0]

        year = one(AcademicYear.objects.filter(school=school, name__iexact=options['academic_year'], is_active=True), 'academic year')
        classroom = one(AcademicClass.objects.filter(section__school=school, section__name__iexact=options['section_name'], section__is_active=True, name__iexact=options['class_name'], is_active=True), 'class')
        streams = {}
        for row in rows:
            if row['classroom'] and row['classroom'].casefold() != classroom.name.casefold():
                raise CommandError(f'CSV row {row["source"]}: class does not match --class-name.')
            if row['stream'] and options.get('stream_name') and row['stream'].casefold() != options['stream_name'].casefold():
                raise CommandError(f'CSV row {row["source"]}: stream does not match --stream-name.')
            stream_name = row['stream'] or options.get('stream_name')
            if not stream_name:
                raise CommandError('Supply a Stream column or --stream-name.')
            key = stream_name.casefold()
            if key not in streams:
                streams[key] = one(Stream.objects.filter(academic_class=classroom, name__iexact=stream_name, is_active=True), f'stream {stream_name}')
            row['stream_key'] = key
        existing = {name_key(student.full_name) for student in Student.objects.filter(school=school)}
        collisions = [row['source'] for row in rows if name_key(row['name']) in existing]
        if collisions:
            raise CommandError('Possible existing students at CSV source rows: ' + ', '.join(collisions) + '. Nothing imported; resolve duplicates first.')
        self.stdout.write(f'Target: {year.name} / {classroom.section.name} / {classroom.name}')
        for key, stream in streams.items():
            self.stdout.write(f'  {stream.name}: {sum(row["stream_key"] == key for row in rows)} students')
        self.stdout.write(f'CSV SHA256: {digest}')
        self.stdout.write(f'Temporary birth date for every learner: {birth}; administrator correction required.')
        self.stdout.write('Enrollment dates use admission dates unless --enrollment-date is specified. No Islamic placements or login accounts are created.')
        for row in rows:
            first, last = row['guardians'][0]
            contact = dict(guardian_first_name=first, guardian_last_name=last, guardian_phone=row['phone'], relationship=row['relationship'])
            matches = Guardian.objects.filter(school=school, first_name__iexact=first, last_name__iexact=last, phone=row['phone'])
            if matches.count() > 1:
                raise CommandError(f'Row {row["source"]}: multiple matching guardian records; resolve before import.')
            if matches.exists():
                contact['existing_guardian'] = matches.get().pk
            data = {key: row[key] for key in ('first_name', 'middle_name', 'last_name', 'gender', 'religion', 'admission_date')}
            data.update(contact, date_of_birth=birth)
            form = StudentRegistrationForm(data, school=school)
            if not form.is_valid():
                raise CommandError(f'Row {row["source"]}: {form.errors.as_text()}')
            student = save_student(form, actor)
            for first, last in row['guardians'][1:]:
                matches = Guardian.objects.filter(school=school, first_name__iexact=first, last_name__iexact=last, phone=row['phone'])
                if matches.count() > 1:
                    raise CommandError(f'Row {row["source"]}: multiple matching guardians.')
                add_guardian_contact(student, dict(existing_guardian=matches.first(), guardian_first_name=first,
                    guardian_last_name=last, guardian_phone=row['phone'], relationship=row['relationship']), actor)
            form = EnrollmentForm(dict(programme='main', academic_year=year.pk, academic_class=classroom.pk,
                stream=streams[row['stream_key']].pk, enrollment_date=enrollment_date or row['admission_date'], status='current'), student=student)
            if not form.is_valid():
                raise CommandError(f'Row {row["source"]}: {form.errors.as_text()}')
            enroll_student(form, actor)
            write_record(student, actor, f'Roster import SHA256 {digest}, source row {row["source"]}. User-authorised TEMPORARY birth date {birth}; school administrator must correct. Name order and relationships retained as supplied. ' + ' '.join(row['warnings']), update_fields=[])
            self.stdout.write(f'Row {row["source"]}: {student.student_id} / {student.full_name}')
            for warning in row['warnings']:
                self.stdout.write('  REVIEW: ' + warning)
        if not options['apply']:
            transaction.set_rollback(True)
        # Announce completion only after the transaction commits/rolls back.
        message = f'Imported {len(rows)} students with guardian contacts and Main enrollments.'
        if options['apply']:
            transaction.on_commit(lambda: self.stdout.write(self.style.SUCCESS(message)))
        else:
            self.stdout.write(f'PREVIEW PASSED: {len(rows)} students validated. No records saved. Preview registration numbers are provisional.')
