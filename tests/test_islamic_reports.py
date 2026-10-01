from copy import deepcopy
from datetime import date

from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.accounts.models import User
from apps.academics.forms import AssessmentForm, MarkForm, SubjectForm
from apps.academics.mark_sheets import all_sheet_assignments, sheet_enrollments, require_approved_sheets
from apps.academics.models import Assessment, AssessmentType, Mark, ReportGroup, Subject
from apps.academics.participation import eligible_enrollments
from apps.academics.permissions import assessment_assignments, visible_assessments
from apps.academics.services import configure_exam_sets, save_academic, save_mark, set_assessment_status
from apps.reports.models import StudentReport
from apps.reports.services import begin_correction, generate_reports, teacher_comment, review_report, publish_report
from apps.students.models import Enrollment, Student
from tests.test_reports import ReportTestCase


class IslamicReportTests(ReportTestCase):
    def setUp(self):
        super().setUp()
        self.student.religion = Student.Religion.MOSLEM
        self.student.save()
        self.other = Student.objects.create(
            school=self.school, student_id='STD-000002', first_name='Other', last_name='Learner',
            gender='male', date_of_birth=date(2018, 1, 1), admission_date=date(2025, 1, 1),
            religion=Student.Religion.CHRISTIAN,
        )
        self.other_enrollment = Enrollment.objects.create(
            student=self.other, academic_year=self.year, section=self.primary,
            academic_class=self.academic_class, stream=self.stream, enrollment_date=date(2026, 1, 2),
        )
        self.islamic_subject = Subject.objects.create(
            section=self.primary, code='QUR', name='Qur’an', report_group=ReportGroup.ISLAMIC,
        )
        self.islamic_assignment = self.assign(subject=self.islamic_subject.pk, stream=self.stream.pk)
        self.islamic = Assessment(
            assessment_type=self.assessment_type, term=self.term, academic_class=self.academic_class,
            date=self.assessment.date, report_group=ReportGroup.ISLAMIC,
            grading_scheme=self.scheme, status='open',
        )
        self.islamic.full_clean()
        self.islamic.save()

    def islamic_mark(self, score='90', exam_set=None):
        form = MarkForm(
            {'score': score, 'expected_revision': 0}, assessment=self.islamic,
            enrollment=self.enrollment, subject=self.islamic_subject,
            assignment=self.islamic_assignment, exam_set=exam_set,
        )
        self.assertTrue(form.is_valid(), form.errors)
        return save_mark(form, self.actor)

    def test_main_and_islamic_assessments_coexist_but_duplicates_fail(self):
        duplicate = Assessment(
            assessment_type=self.assessment_type, term=self.term, academic_class=self.academic_class,
            date=self.assessment.date, report_group='islamic',
        )
        with self.assertRaises(ValidationError):
            duplicate.full_clean()
        self.assertEqual(Assessment.objects.count(), 2)

    def test_only_islam_students_on_roster_and_only_matching_subjects(self):
        self.assertQuerySetEqual(eligible_enrollments(self.islamic), [self.enrollment], ordered=False)
        self.assertEqual(eligible_enrollments(self.assessment).count(), 2)
        self.assertQuerySetEqual(all_sheet_assignments(self.islamic), [self.islamic_assignment])
        self.assertQuerySetEqual(all_sheet_assignments(self.assessment), [self.assignment])
        self.assertQuerySetEqual(sheet_enrollments(self.islamic, self.islamic_assignment), [self.enrollment])
        self.assertFalse(sheet_enrollments(self.islamic, self.assignment).exists())
        self.assertFalse(assessment_assignments(self.assessment, self.actor, subject=self.islamic_subject).exists())

    def test_other_and_blank_religions_are_excluded(self):
        for religion in (Student.Religion.CHRISTIAN, Student.Religion.OTHER, ''):
            self.other.religion = religion
            self.other.save()
            self.assertFalse(eligible_enrollments(self.islamic).filter(student=self.other).exists())

    def test_forged_non_muslim_mark_and_cross_group_mark_rejected(self):
        for assessment, enrollment, subject, assignment in (
            (self.islamic, self.other_enrollment, self.islamic_subject, self.islamic_assignment),
            (self.assessment, self.enrollment, self.islamic_subject, self.islamic_assignment),
            (self.islamic, self.enrollment, self.subject, self.assignment),
        ):
            mark = Mark(assessment=assessment, enrollment=enrollment, subject=subject,
                        teaching_assignment=assignment, score=70)
            with self.assertRaises(ValidationError):
                mark.full_clean()
        self.client.force_login(self.actor)
        url = reverse('academics:mark_form', args=[self.islamic.pk, self.islamic_subject.pk, self.other_enrollment.pk])
        self.assertEqual(self.client.post(url, {'score': 70, 'expected_revision': 0}).status_code, 404)
        self.assertFalse(Mark.objects.exists())

    def test_reports_and_ranking_are_separate(self):
        self.school.enable_ranking = True
        self.school.save()
        self.mark('75')
        form = MarkForm({'score': '95', 'expected_revision': 0}, assessment=self.assessment,
                        enrollment=self.other_enrollment, subject=self.subject, assignment=self.assignment)
        self.assertTrue(form.is_valid(), form.errors)
        save_mark(form, self.actor)
        self.islamic_mark('90')
        main = generate_reports(set_assessment_status(self.assessment, 'closed', self.actor), self.actor)
        islamic = generate_reports(set_assessment_status(self.islamic, 'closed', self.actor), self.actor)
        self.assertEqual(len(main), 2)
        self.assertEqual(len(islamic), 1)
        main_report = next(r for r in main if r.enrollment_id == self.enrollment.pk)
        self.assertEqual(main_report.snapshot['average'], '75.00')
        self.assertEqual(main_report.snapshot['position'], 2)
        data = islamic[0].snapshot
        self.assertEqual((data['average'], data['position'], data['cohort_size']), ('90.00', 1, 1))
        self.assertEqual([r['subject_id'] for r in data['subjects']], [self.islamic_subject.pk])
        self.assertEqual([r['subject_id'] for r in main_report.snapshot['subjects']], [self.subject.pk])
        self.assertIn('Islamic Studies', data['assessment'])

    def test_religion_edit_preserves_history_and_corrections_but_not_future_eligibility(self):
        self.islamic_mark()
        report = generate_reports(set_assessment_status(self.islamic, 'closed', self.actor), self.actor)[0]
        report = teacher_comment(report, 'Good progress', self.actor)
        report = review_report(report, 'Keep it up', True, self.users[User.Role.HEADTEACHER])
        report = publish_report(report, self.actor)
        snapshot = deepcopy(report.snapshot)
        self.student.religion = Student.Religion.CHRISTIAN
        self.student.save()
        report.refresh_from_db()
        self.assertEqual(report.snapshot, snapshot)
        corrected = begin_correction(self.islamic, 'Correct mark', self.actor)
        regenerated = generate_reports(set_assessment_status(corrected, 'closed', self.actor), self.actor)[0]
        self.assertEqual(regenerated.enrollment_id, self.enrollment.pk)
        another_type = AssessmentType.objects.create(school=self.school, name='Another term exam')
        future = Assessment.objects.create(assessment_type=another_type, term=self.term,
            academic_class=self.academic_class, date=self.assessment.date, report_group='islamic')
        self.assertFalse(eligible_enrollments(future).exists())

    def test_used_subject_and_assessment_group_cannot_be_reassigned(self):
        self.islamic_mark()
        self.islamic_subject.report_group = 'main'
        with self.assertRaises(ValidationError):
            self.islamic_subject.full_clean()
        self.islamic.report_group = 'main'
        with self.assertRaises(ValidationError):
            self.islamic.full_clean()

    def test_two_exam_sets_need_only_islamic_students_and_subjects(self):
        self.islamic.two_exam_sets = True
        self.islamic.save()
        configure_exam_sets(self.islamic, self.actor)
        for exam_set in self.islamic.exam_sets.all():
            self.islamic_mark('80' if exam_set.number == 1 else '100', exam_set)
        require_approved_sheets(self.islamic)
        report = generate_reports(set_assessment_status(self.islamic, 'closed', self.actor), self.actor)[0]
        self.assertEqual(report.snapshot['average'], '90.00')
        self.assertEqual(len(report.snapshot['subjects']), 1)

    def test_midterm_and_endterm_render_islamic_title(self):
        self.assessment_type.name = 'End-Term'
        self.assessment_type.save()
        self.islamic_mark()
        report = generate_reports(set_assessment_status(self.islamic, 'closed', self.actor), self.actor)[0]
        self.client.force_login(self.actor)
        self.assertContains(self.client.get(reverse('reports:print', args=[report.pk])), 'Islamic Studies')
        response = self.client.get(reverse('reports:pdf', args=[report.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))
        mid_type = AssessmentType.objects.create(school=self.school, name='Mid-Term', screen_only_report=True)
        self.islamic = Assessment.objects.create(assessment_type=mid_type, term=self.term,
            academic_class=self.academic_class, date=self.assessment.date, report_group='islamic',
            grading_scheme=self.scheme, status='open')
        self.islamic_mark()
        mid = generate_reports(set_assessment_status(self.islamic, 'closed', self.actor), self.actor)[0]
        response = self.client.get(reverse('reports:detail', args=[mid.pk]))
        self.assertContains(response, 'Islamic Studies / Mid-Term')
        self.assertTemplateUsed(response, 'reports/midterm.html')

    def test_subject_group_can_be_selected_before_marks(self):
        form = SubjectForm({'section': self.primary.pk, 'code': 'FIQH', 'name': 'Fiqh',
                            'report_group': 'islamic'}, school=self.school, actor=self.actor)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(save_academic(form, self.actor).report_group, 'islamic')

    def test_teacher_without_islamic_assignment_cannot_access_assessment(self):
        self.class_teacher.is_active = False
        self.class_teacher.save()
        self.islamic_assignment.is_active = False
        self.islamic_assignment.save()
        self.assertFalse(visible_assessments(self.teacher.user).filter(pk=self.islamic.pk).exists())

    def test_assessment_form_saves_group_and_keeps_existing_group_on_edit(self):
        other_type = AssessmentType.objects.create(school=self.school, name='End-Term')
        data = {'assessment_type': other_type.pk, 'report_group': 'islamic', 'term': self.term.pk,
                'academic_class': self.academic_class.pk, 'stream': '',
                'date': self.assessment.date.isoformat(), 'maximum_score': '100'}
        form = AssessmentForm(data, school=self.school, actor=self.actor)
        self.assertTrue(form.is_valid(), form.errors)
        record = save_academic(form, self.actor)
        self.assertEqual(record.report_group, 'islamic')
        data['report_group'] = 'main'
        form = AssessmentForm(data, instance=record, school=self.school, actor=self.actor)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(save_academic(form, self.actor).report_group, 'islamic')

    def test_non_muslim_report_cannot_be_created_directly(self):
        report = StudentReport(assessment=self.islamic, enrollment=self.other_enrollment)
        with self.assertRaisesMessage(ValidationError, 'not eligible'):
            report.full_clean()

    def test_roster_page_excludes_non_muslims_and_main_subjects(self):
        self.client.force_login(self.actor)
        response = self.client.get(reverse('academics:marks', args=[self.islamic.pk]))
        self.assertContains(response, self.student.full_name)
        self.assertNotContains(response, self.other.full_name)
        self.assertContains(response, 'Islamic Studies')
        self.assertNotContains(response, self.subject.name)
