from copy import deepcopy
from unittest.mock import patch
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client
from django.urls import reverse
from apps.accounts.models import User
from apps.academics.models import ClassTeacherAssignment, Subject, TeachingAssignment
from apps.academics.services import set_assessment_status
from apps.reports.models import StudentReport
from apps.reports.services import begin_correction, generate_reports, publish_report, review_report, teacher_comment
from tests.test_grading import GradingTestCase


class ReportTestCase(GradingTestCase):
    def setUp(self):
        super().setUp()
        self.class_teacher = ClassTeacherAssignment.objects.create(teacher=self.teacher, academic_year=self.year, term=self.term, section=self.primary, academic_class=self.academic_class, stream=self.stream)

    def generated(self):
        self.mark()
        self.assessment = set_assessment_status(self.assessment, 'closed', self.actor)
        return generate_reports(self.assessment, self.actor)[0]

    def published(self):
        report = self.generated()
        report = teacher_comment(report, 'Good progress.', self.teacher.user)
        report = review_report(report, 'Continue working hard.', True, self.users[User.Role.HEADTEACHER])
        return publish_report(report, self.actor)


class ReportTests(ReportTestCase):
    def test_complete_review_publication_workflow(self):
        report = self.published()
        self.assertEqual(report.status, 'published')
        self.assertIsNotNone(report.published_at)
        self.assertEqual(report.snapshot['student'], 'Mary Wasswa')
        self.assertEqual(report.snapshot['aggregate'], 1)
        self.assertIsNone(report.snapshot['position'])

    def test_missing_marks_and_unconfigured_assessment_cannot_generate(self):
        self.assessment = set_assessment_status(self.assessment, 'closed', self.actor)
        with self.assertRaisesMessage(ValidationError, 'Complete all assigned'):
            generate_reports(self.assessment, self.actor)
        self.assertFalse(StudentReport.objects.exists())

    def test_deactivating_assignment_cannot_hide_missing_subject(self):
        self.mark()
        subject = Subject.objects.create(section=self.primary, code='MATH', name='Math')
        TeachingAssignment.objects.create(teacher=self.teacher, academic_year=self.year, term=self.term, section=self.primary, academic_class=self.academic_class, subject=subject, is_active=False)
        self.assessment = set_assessment_status(self.assessment, 'closed', self.actor)
        with self.assertRaises(ValidationError):
            generate_reports(self.assessment, self.actor)

    def test_published_data_preserves_names_and_blocks_modification(self):
        report = self.published()
        before = deepcopy(report.snapshot)
        self.student.first_name = 'Changed'
        self.student.save()
        self.subject.name = 'Renamed'
        self.subject.save()
        report.refresh_from_db()
        self.assertEqual(report.snapshot, before)
        report.teacher_comment = 'Tampered'
        with self.assertRaises(ValidationError):
            report.full_clean()
        with self.assertRaises(ValidationError):
            set_assessment_status(self.assessment, 'open', self.actor)

    def test_correction_creates_new_version_without_changing_published_copy(self):
        previous = self.published()
        snapshot = deepcopy(previous.snapshot)
        begin_correction(self.assessment, 'Correct transcription error.', self.actor)
        previous.refresh_from_db()
        self.assertFalse(previous.is_current)
        self.assertEqual(previous.snapshot, snapshot)
        current = StudentReport.objects.get(is_current=True)
        self.assertEqual((current.version, current.previous_id, current.snapshot), (2, previous.pk, {}))
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.status, 'open')

    def test_comment_assignment_and_approval_separation(self):
        report = self.generated()
        self.class_teacher.is_active = False
        self.class_teacher.save()
        with self.assertRaises(PermissionDenied):
            teacher_comment(report, 'Comment', self.teacher.user)
        report = teacher_comment(report, 'Admin override', self.actor)
        with self.assertRaises(PermissionDenied):
            review_report(report, 'Not a headteacher', True, self.actor)
        report = review_report(report, 'Please clarify.', False, self.users[User.Role.HEADTEACHER])
        self.assertEqual(report.status, 'draft')
        with self.assertRaises(ValidationError):
            publish_report(report, self.actor)

    def test_generation_audit_failure_rolls_back_batch(self):
        self.mark()
        self.assessment = set_assessment_status(self.assessment, 'closed', self.actor)
        with patch('apps.schools.services.LogEntry.objects.create', side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):
                generate_reports(self.assessment, self.actor)
        self.assertFalse(StudentReport.objects.exists())

    def test_html_pdf_and_print_authorize_every_request(self):
        report = self.published()
        for role in (User.Role.BURSAR, User.Role.STUDENT):
            self.client.force_login(self.users[role])
            for name in ('detail', 'print', 'pdf'):
                self.assertEqual(self.client.get(reverse('reports:' + name, args=[report.pk])).status_code, 403 if role == User.Role.BURSAR else 404)
        self.client.force_login(self.teacher.user)
        for name in ('detail', 'print'):
            self.assertContains(self.client.get(reverse('reports:' + name, args=[report.pk])), 'Mary Wasswa')
        response = self.client.get(reverse('reports:pdf', args=[report.pk]))
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn('no-store', response['Cache-Control'])
        self.assignment.is_active = False
        self.assignment.save()
        self.class_teacher.is_active = False
        self.class_teacher.save()
        self.assertEqual(self.client.get(reverse('reports:pdf', args=[report.pk])).status_code, 404)

    def test_csrf_and_report_html_escapes_comments(self):
        report = self.generated()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.teacher.user)
        self.assertEqual(client.post(reverse('reports:comment', args=[report.pk]), {'comment': 'Hi'}).status_code, 403)
        teacher_comment(report, '<script>alert(1)</script>', self.teacher.user)
        self.client.force_login(self.actor)
        response = self.client.get(reverse('reports:detail', args=[report.pk]))
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
