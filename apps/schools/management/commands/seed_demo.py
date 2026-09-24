"""Explicit development-only sample school, created through validated services."""
from datetime import date
from decimal import Decimal
import os
from uuid import uuid4
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import User
from apps.academics.forms import MarkForm
from apps.academics.models import Assessment, AssessmentType, ClassTeacherAssignment, DivisionRule, GradeRule, GradingScheme, Subject, Teacher, TeachingAssignment
from apps.academics.services import save_mark, set_academic_active, set_assessment_status
from apps.academics.mark_sheets import SheetReviewForm, all_sheet_assignments, review_sheet, sheet_snapshot
from apps.academics.models import MarkSubmission
from apps.expenses.forms import ExpenseForm, IncomeForm
from apps.expenses.models import ExpenseCategory
from apps.expenses.services import record_cash
from apps.finance.models import FeeStructure
from apps.finance.services import assign_charge, record_payment
from apps.promotions.forms import BatchForm
from apps.promotions.services import create_batch, save_decisions
from apps.reports.services import generate_reports, publish_report, review_report, teacher_comment
from apps.schools.models import AcademicClass, AcademicYear, School, Section, Stream, Term
from apps.schools.services import set_current_period, write_record
from apps.students.forms import EnrollmentForm, StudentRegistrationForm
from apps.students.models import Guardian
from apps.students.services import enroll_student, save_student


class Command(BaseCommand):
    help = 'Create an explicit demo school in an unconfigured development database. Password is read from an environment variable.'

    def add_arguments(self, parser):
        parser.add_argument('--password-env', default='NIHAD_DEMO_PASSWORD')

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Demo data is disabled outside development settings.')
        if School.objects.exists():
            raise CommandError('Demo seeding requires an unconfigured database; existing school data is never overwritten.')
        password = os.environ.get(options['password_env'], '')
        if not password:
            raise CommandError('Set the selected demo password environment variable first.')
        validate_password(password)
        names = {'super_admin': 'demo-super', 'school_admin': 'demo-admin', 'headteacher': 'demo-headteacher', 'teacher': 'demo-teacher', 'bursar': 'demo-bursar', 'guardian': 'demo-guardian'}
        if not settings.GUARDIAN_ACCOUNTS_ENABLED:
            names.pop(User.Role.GUARDIAN)
        if User.objects.filter(username__in=names.values()).exists():
            raise CommandError('A demo username already exists. Use a fresh development database.')
        users = {}
        for role, username in names.items():
            create = User.objects.create_superuser if role == User.Role.SUPER_ADMIN else User.objects.create_user
            users[role] = create(username=username, role=role, password=password, email=username + '@example.test', first_name='Demo', last_name=User.Role(role).label, must_change_password=True)
        actor = users[User.Role.SCHOOL_ADMIN]
        def save(record):
            return write_record(record, actor, 'Created explicit development demo record.')
        today, number = timezone.localdate(), timezone.localdate().year
        school = save(School(name='NIHAD Demo School', motto='Learning with confidence', currency_code='UGX', enable_ranking=True))
        primary = save(Section(school=school, name='Primary', sort_order=2))
        nursery = save(Section(school=school, name='Nursery', sort_order=1))
        classroom = save(AcademicClass(section=primary, name='P.5', sort_order=5))
        next_class = save(AcademicClass(section=primary, name='P.6', sort_order=6))
        baby = save(AcademicClass(section=nursery, name='Baby', sort_order=1))
        stream = save(Stream(academic_class=classroom, name='East'))
        save(Stream(academic_class=classroom, name='West'))
        year = save(AcademicYear(school=school, name=str(number), start_date=date(number, 1, 1), end_date=date(number, 12, 31)))
        next_year = save(AcademicYear(school=school, name=str(number + 1), start_date=date(number + 1, 1, 1), end_date=date(number + 1, 12, 31)))
        terms = [save(Term(academic_year=year, name=name, start_date=start, end_date=end)) for name, start, end in [('Term 1', date(number, 1, 1), date(number, 5, 31)), ('Term 2', date(number, 6, 1), date(number, 8, 31)), ('Term 3', date(number, 9, 1), date(number, 12, 31))]]
        term = next(item for item in terms if item.start_date <= today <= item.end_date)
        set_current_period(actor, year, term)
        teacher = save(Teacher(school=school, user=users[User.Role.TEACHER], phone='0700000001', date_joined=year.start_date))
        subjects = [save(Subject(section=primary, code=code, name=name)) for code, name in [('ENG', 'English'), ('MATH', 'Mathematics')]]
        assignments = [save(TeachingAssignment(teacher=teacher, academic_year=year, term=term, section=primary, academic_class=classroom, stream=stream, subject=subject)) for subject in subjects]
        save(ClassTeacherAssignment(teacher=teacher, academic_year=year, term=term, section=primary, academic_class=classroom, stream=stream))
        learning = save(Subject(section=nursery, code='COMM', name='Communication'))
        nursery_assignment = save(TeachingAssignment(teacher=teacher, academic_year=year, term=term, section=nursery, academic_class=baby, subject=learning))
        save(ClassTeacherAssignment(teacher=teacher, academic_year=year, term=term, section=nursery, academic_class=baby))
        scheme = save(GradingScheme(section=primary, name='Demo numeric grading', aggregate_mode='all'))
        for label, low, high, points in [('F9', 0, 60, 9), ('D2', 60, 80, 2), ('D1', 80, 100, 1)]:
            save(GradeRule(scheme=scheme, label=label, minimum=low, maximum=high, points=points))
        save(DivisionRule(scheme=scheme, label='I', minimum=2, maximum=4))
        save(DivisionRule(scheme=scheme, label='II', minimum=5, maximum=12))
        scheme = set_academic_active(scheme, True, actor)
        descriptive = save(GradingScheme(section=nursery, name='Demo learning levels', mode='descriptive'))
        levels = [save(GradeRule(scheme=descriptive, label=label, sort_order=index)) for index, label in enumerate(['Emerging', 'Developing', 'Achieved', 'Excellent'])]
        descriptive = set_academic_active(descriptive, True, actor)
        guardian = save(Guardian(school=school, user=users.get(User.Role.GUARDIAN), first_name='Jane', last_name='Demo', email='demo-guardian@example.test', phone='0700000002'))
        enrollments = []
        for index, name in enumerate(['Mary', 'John', 'Sarah']):
            form = StudentRegistrationForm({'first_name': name, 'last_name': 'Demo', 'gender': 'male' if index == 1 else 'female', 'date_of_birth': date(number - (4 if index == 2 else 10), 1, 1), 'admission_date': year.start_date, 'existing_guardian': guardian.pk, 'relationship': 'Parent'}, school=school)
            if not form.is_valid():
                raise CommandError(str(form.errors))
            student = save_student(form, actor)
            form = EnrollmentForm({'academic_year': year.pk, 'academic_class': baby.pk if index == 2 else classroom.pk, 'stream': '' if index == 2 else stream.pk, 'enrollment_date': year.start_date, 'status': 'current'}, student=student)
            if not form.is_valid():
                raise CommandError(str(form.errors))
            enrollments.append(enroll_student(form, actor))
        kind = save(AssessmentType(school=school, name='Mid-Term'))
        save(AssessmentType(school=school, name='End-Term'))
        primary_assessment = save(Assessment(assessment_type=kind, term=term, academic_class=classroom, stream=stream, date=today, grading_scheme=scheme, status='open'))
        nursery_assessment = save(Assessment(assessment_type=kind, term=term, academic_class=baby, date=today, grading_scheme=descriptive, status='open'))
        for index, enrollment in enumerate(enrollments):
            for assignment in ([nursery_assignment] if index == 2 else assignments):
                assessment = nursery_assessment if index == 2 else primary_assessment
                data = {'expected_revision': 0, 'level': levels[2].pk} if index == 2 else {'expected_revision': 0, 'score': str(86 - index * 15)}
                form = MarkForm(data, assessment=assessment, enrollment=enrollment, subject=assignment.subject, assignment=assignment)
                if not form.is_valid():
                    raise CommandError(str(form.errors))
                save_mark(form, users[User.Role.TEACHER])
        for assessment in (primary_assessment, nursery_assessment):
            for assignment in all_sheet_assignments(assessment):
                submission = save(MarkSubmission(assessment=assessment, assignment=assignment,
                    status='submitted', revision=1, submitted_by=users[User.Role.TEACHER],
                    submitted_at=timezone.now(), snapshot=sheet_snapshot(assessment, assignment)))
                review = SheetReviewForm({'action': 'approve', 'note': 'Demo marks checked.', 'revision': submission.revision})
                if not review.is_valid():
                    raise CommandError(str(review.errors))
                review_sheet(assessment, assignment, review, users[User.Role.HEADTEACHER])
            assessment = set_assessment_status(assessment, 'closed', actor)
            for report in generate_reports(assessment, actor):
                report = teacher_comment(report, 'Steady progress this term. Keep practising.', users[User.Role.TEACHER])
                report = review_report(report, 'Continue learning with confidence.', True, users[User.Role.HEADTEACHER])
                publish_report(report, actor)
        structure = save(FeeStructure(term=term, academic_class=classroom, name='Tuition', amount=Decimal('50000'), due_date=term.start_date))
        charges = [assign_charge(enrollment, structure, users[User.Role.BURSAR]) for enrollment in enrollments[:2]]
        record_payment(charges[0], {'amount': Decimal('20000'), 'date': today, 'method': 'cash', 'reference': '', 'notes': 'Demo partial payment', 'request_key': uuid4()}, users[User.Role.BURSAR])
        category = save(ExpenseCategory(school=school, name='Stationery'))
        for form in [ExpenseForm({'category': category.pk, 'description': 'Demo exercise books', 'amount': '3000', 'date': today, 'method': 'cash', 'request_key': uuid4(), 'confirm': True}), IncomeForm({'source': 'Donation', 'description': 'Demo school donation', 'amount': '5000', 'date': today, 'method': 'cash', 'request_key': uuid4(), 'confirm': True})]:
            if not form.is_valid():
                raise CommandError(str(form.errors))
            record_cash(form, users[User.Role.BURSAR])
        form = BatchForm({'source_year': year.pk, 'source_class': classroom.pk, 'source_stream': stream.pk, 'completion_date': year.end_date, 'destination_year': next_year.pk, 'destination_class': next_class.pk, 'enrollment_date': next_year.start_date})
        if not form.is_valid():
            raise CommandError(str(form.errors))
        batch = create_batch(form, actor)
        save_decisions(batch, [{'enrollment': enrollment, 'selected': True, 'decision': 'promoted'} for enrollment in enrollments[:2]], 0, actor)
        self.stdout.write(self.style.SUCCESS('Demo school created. Individual logins: ' + ', '.join(names.values()) + '. Each account must change its temporary password.'))
