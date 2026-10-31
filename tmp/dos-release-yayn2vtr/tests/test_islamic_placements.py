from datetime import date
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import connection, IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.academics.forms import ClassTeacherAssignmentForm, MarkForm
from apps.academics.models import Assessment, ClassTeacherAssignment, Mark, MarkSubmission, Subject, Teacher
from apps.academics.participation import eligible_enrollments
from apps.academics.permissions import visible_enrollments
from apps.academics.services import save_academic, save_mark, set_assessment_status
from apps.finance.models import FeeCharge, FeeStructure
from apps.finance.services import assign_charge, assign_class_charges
from apps.promotions.forms import BatchForm
from apps.promotions.services import create_batch, save_decisions, confirm_batch, eligible_enrollments as promotion_roster
from apps.reports.models import StudentReport
from apps.reports.permissions import can_comment, visible_reports
from apps.reports.services import generate_reports
from apps.schools.models import AcademicClass
from apps.students.forms import EnrollmentForm
from apps.students.models import Enrollment, Student
from apps.students.services import enroll_student, close_enrollment
from tests.test_reports import ReportTestCase


class IslamicPlacementTests(ReportTestCase):
    def setUp(self):
        super().setUp()
        self.student.religion = Student.Religion.MOSLEM
        self.student.save()
        self.islamic_class = AcademicClass.objects.create(section=self.primary, name='P.3 Islamic', sort_order=3)
        self.islamic_enrollment = self.enroll(programme='islamic', academic_class=self.islamic_class.pk)
        self.islamic_subject = Subject.objects.create(section=self.primary, name='Fiqh', code='FIQH', report_group='islamic')
        user = User.objects.create_user(username='islamic_teacher', role=User.Role.TEACHER)
        self.islamic_teacher = Teacher.objects.create(user=user, school=self.school, phone='0700', date_joined=date(2025, 1, 1))
        self.islamic_assignment = self.assign(teacher=self.islamic_teacher.pk, academic_class=self.islamic_class.pk,
                                              subject=self.islamic_subject.pk)
        self.islamic = Assessment.objects.create(assessment_type=self.assessment_type, term=self.term,
            academic_class=self.islamic_class, date=self.assessment.date, report_group='islamic',
            status='open', grading_scheme=self.scheme, requires_mark_review=False)

    def islamic_result(self):
        form = MarkForm({'score': '88', 'expected_revision': 0}, assessment=self.islamic,
                        enrollment=self.islamic_enrollment, subject=self.islamic_subject,
                        assignment=self.islamic_assignment)
        self.assertTrue(form.is_valid(), form.errors)
        return save_mark(form, self.islamic_teacher.user)

    def test_separate_classes_rosters_marks_reports_and_teacher_permissions(self):
        self.assertQuerySetEqual(eligible_enrollments(self.assessment), [self.enrollment])
        self.assertQuerySetEqual(eligible_enrollments(self.islamic), [self.islamic_enrollment])
        self.assertQuerySetEqual(visible_enrollments(self.teacher.user), [self.enrollment])
        self.assertQuerySetEqual(visible_enrollments(self.islamic_teacher.user), [self.islamic_enrollment])
        self.islamic_result()
        report = generate_reports(set_assessment_status(self.islamic, 'closed', self.actor), self.actor)[0]
        self.assertEqual(report.snapshot['class'], self.islamic_class.name)
        self.assertFalse(visible_reports(self.teacher.user).filter(pk=report.pk).exists())
        self.assertTrue(visible_reports(self.islamic_teacher.user).filter(pk=report.pk).exists())
        self.assertFalse(can_comment(self.islamic_teacher.user, report))
        form = ClassTeacherAssignmentForm(self.assignment_data(teacher=self.islamic_teacher.pk,
            academic_class=self.islamic_class.pk, report_group='islamic'), school=self.school, actor=self.actor)
        self.assertTrue(form.is_valid(), form.errors)
        save_academic(form, self.actor)
        self.assertTrue(can_comment(self.islamic_teacher.user, report))
        main = self.generated()
        self.assertEqual(main.snapshot['class'], self.academic_class.name)
        self.client.force_login(self.islamic_teacher.user)
        self.assertEqual(self.client.get(reverse('academics:marks', args=[self.assessment.pk])).status_code, 404)
        self.client.force_login(self.teacher.user)
        self.assertEqual(self.client.get(reverse('academics:marks', args=[self.islamic.pk])).status_code, 404)

    def test_programme_uniqueness_and_history_are_independent(self):
        form = EnrollmentForm(self.enrollment_data(programme='islamic', academic_class=self.islamic_class.pk), student=self.student)
        self.assertFalse(form.is_valid())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Enrollment.objects.create(student=self.student, academic_year=self.year, section=self.primary,
                                      academic_class=self.islamic_class, programme='islamic')
        close_enrollment(self.islamic_enrollment, 'completed', date(2026, 2, 1), self.actor)
        moved = self.enroll(programme='islamic', enrollment_date='2026-02-02')
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, 'current')
        self.assertEqual(moved.academic_class_id, self.academic_class.pk)
        self.islamic_enrollment.refresh_from_db()
        self.islamic_enrollment.programme = 'main'
        with self.assertRaises(ValidationError):
            self.islamic_enrollment.full_clean()

    def test_muslim_student_needs_placement_and_same_class_programmes_stay_isolated(self):
        self.islamic_enrollment.delete()  # Empty fixture.
        self.assertFalse(eligible_enrollments(self.islamic).exists())
        islamic = self.enroll(programme='islamic', stream=self.stream.pk)
        self.islamic.academic_class = self.academic_class
        self.islamic.save()
        self.assertQuerySetEqual(eligible_enrollments(self.islamic), [islamic])
        self.assertQuerySetEqual(visible_enrollments(self.teacher.user), [self.enrollment])
        self.client.force_login(self.teacher.user)
        self.assertEqual(self.client.get(reverse('academics:marks', args=[self.islamic.pk])).status_code, 404)
        form = ClassTeacherAssignmentForm(self.assignment_data(teacher=self.islamic_teacher.pk,
            stream=self.stream.pk, report_group='islamic'), school=self.school, actor=self.actor)
        self.assertTrue(form.is_valid(), form.errors)
        assignment = save_academic(form, self.actor)
        self.assertQuerySetEqual(visible_enrollments(self.islamic_teacher.user), [islamic])
        duplicate = ClassTeacherAssignmentForm(self.assignment_data(teacher=self.islamic_teacher.pk,
            stream=self.stream.pk, report_group='islamic'), school=self.school, actor=self.actor)
        self.assertFalse(duplicate.is_valid())
        edit = ClassTeacherAssignmentForm(instance=assignment, school=self.school, actor=self.actor)
        self.assertTrue(edit.fields['report_group'].disabled)
        forged = Mark(assessment=self.islamic, enrollment=self.enrollment,
                      subject=self.islamic_subject, teaching_assignment=self.islamic_assignment, score=88)
        with self.assertRaisesMessage(ValidationError, 'not eligible'):
            forged.full_clean()

    def test_religion_required_at_form_and_service_even_after_form_validation(self):
        close_enrollment(self.islamic_enrollment, 'completed', date(2026, 2, 1), self.actor)
        form = EnrollmentForm(self.enrollment_data(programme='islamic', enrollment_date='2026-02-02'), student=self.student)
        self.assertTrue(form.is_valid(), form.errors)
        Student.objects.filter(pk=self.student.pk).update(religion='Christian')
        with self.assertRaisesMessage(ValidationError, 'Only students'):
            enroll_student(form, self.actor)
        self.student.refresh_from_db()
        form = EnrollmentForm(self.enrollment_data(programme='islamic'), student=self.student)
        self.assertFalse(form.is_valid())
        self.assertFalse(eligible_enrollments(self.islamic).exists())

    def test_school_admin_form_and_programme_filter(self):
        self.client.force_login(self.actor)
        self.assertContains(self.client.get(reverse('students:enroll', args=[self.student.pk])), 'Islamic Studies')
        response = self.client.get(reverse('students:list'), {'programme': 'islamic', 'class': self.islamic_class.pk})
        self.assertContains(response, self.student.full_name)
        self.assertContains(response, 'Islamic Studies')
        response = self.client.get(reverse('students:list'), {'programme': 'main', 'class': self.islamic_class.pk})
        self.assertNotContains(response, self.student.full_name)
        self.client.force_login(self.islamic_teacher.user)
        self.assertEqual(self.client.post(reverse('students:enroll', args=[self.student.pk]), {}).status_code, 403)

    def test_finance_uses_main_only_even_when_classes_match(self):
        # Use another Muslim student with matching class placements to exercise bulk billing.
        other = Student.objects.create(school=self.school, student_id='DUAL-2', first_name='Dual', last_name='Learner',
            religion='Moslem', gender='male', admission_date=date(2025, 1, 1), date_of_birth=date(2018, 1, 1))
        main = Enrollment.objects.create(student=other, academic_year=self.year, section=self.primary,
            academic_class=self.academic_class, enrollment_date=date(2026, 1, 2))
        islamic = Enrollment.objects.create(student=other, academic_year=self.year, section=self.primary,
            academic_class=self.academic_class, enrollment_date=date(2026, 1, 2), programme='islamic')
        structure = FeeStructure.objects.create(term=self.term, academic_class=self.academic_class,
            name='Tuition', amount=100, due_date=date(2026, 3, 1))
        assign_class_charges(structure, self.actor)
        self.assertEqual(set(FeeCharge.objects.values_list('enrollment_id', flat=True)), {main.pk, self.enrollment.pk})
        with self.assertRaisesMessage(ValidationError, 'Main enrollment'):
            assign_charge(islamic, structure, self.actor)

    def test_islamic_promotion_does_not_change_main_or_student_status(self):
        destination = AcademicClass.objects.create(section=self.primary, name='P.4 Islamic', sort_order=4)
        form = BatchForm({'programme': 'islamic', 'source_year': self.year.pk, 'source_class': self.islamic_class.pk,
            'completion_date': '2026-12-31', 'destination_year': self.next_year.pk,
            'destination_class': destination.pk, 'enrollment_date': '2027-01-02'})
        self.assertTrue(form.is_valid(), form.errors)
        batch = create_batch(form, self.actor)
        self.assertQuerySetEqual(promotion_roster(batch), [self.islamic_enrollment])
        batch = save_decisions(batch, [{'enrollment': self.islamic_enrollment, 'selected': True,
                                       'decision': 'promoted'}], 0, self.actor)
        confirm_batch(batch, batch.revision, self.actor)
        new = batch.decisions.get().new_enrollment
        self.assertEqual((new.programme, new.academic_class_id), ('islamic', destination.pk))
        self.enrollment.refresh_from_db()
        self.student.refresh_from_db()
        self.assertEqual(self.enrollment.status, 'current')
        self.assertEqual(self.student.status, 'active')

    def test_legacy_migration_preserves_marks_snapshots_and_sheet_approval(self):
        self.islamic_enrollment.delete()  # Empty fixture only; simulate the pre-migration schema data.
        self.islamic.academic_class = self.academic_class
        self.islamic.save()
        mark = Mark.objects.create(assessment=self.islamic, enrollment=self.enrollment,
            subject=self.islamic_subject, teaching_assignment=self.islamic_assignment, score=88)
        snapshot = {'class': self.academic_class.name, 'total': '88', 'report_group': 'islamic'}
        report = StudentReport.objects.create(assessment=self.islamic, enrollment=self.enrollment,
            snapshot=snapshot, status='published', published_at=timezone.now())
        sheet = MarkSubmission.objects.create(assessment=self.islamic, assignment=self.islamic_assignment,
            status='approved', snapshot=[[self.enrollment.pk, mark.revision]])
        migration = import_module('apps.students.migrations.0011_preserve_islamic_enrollment_history')
        migration.preserve_history(apps, SimpleNamespace(connection=connection))
        mark.refresh_from_db(); report.refresh_from_db(); sheet.refresh_from_db()
        self.assertEqual(mark.enrollment.programme, 'islamic')
        self.assertEqual(mark.enrollment.academic_class_id, self.enrollment.academic_class_id)
        self.assertEqual(mark.score, 88)
        self.assertEqual(report.enrollment_id, mark.enrollment_id)
        self.assertEqual(report.snapshot, snapshot)
        self.assertEqual(report.status, 'published')
        self.assertEqual(sheet.status, 'approved')
        self.assertEqual(sheet.snapshot, [[mark.enrollment_id, mark.revision]])
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.programme, 'main')
        self.assertTrue(ClassTeacherAssignment.objects.filter(report_group='islamic', teacher=self.class_teacher.teacher,
                                                              academic_class=self.academic_class).exists())
