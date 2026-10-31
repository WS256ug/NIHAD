from decimal import Decimal
from copy import deepcopy
from django.core.exceptions import ValidationError
from django.urls import reverse
from apps.accounts.models import User
from apps.academics.forms import AssessmentForm, MarkForm
from apps.academics.models import AssessmentType, Mark, MarkSubmission
from apps.academics.services import save_academic, save_mark, set_assessment_status
from apps.reports.services import generate_reports, begin_correction
from apps.reports.pdf import report_pdf
from tests.test_reports import ReportTestCase


class ExamSetTests(ReportTestCase):
    def setUp(self):
        super().setUp()
        self.midterm = self.assessment
        self.mark()
        kind = AssessmentType.objects.create(school=self.school, name='End-Term', two_exam_sets=True)
        data = {'assessment_type': kind.pk, 'term': self.term.pk, 'academic_class': self.academic_class.pk,
                'stream': self.stream.pk, 'date': self.assessment.date, 'maximum_score': 100, 'set_one_weight': 50}
        form = AssessmentForm(data, school=self.school, actor=self.actor)
        self.assertTrue(form.is_valid(), form.errors)
        self.assessment = save_academic(form, self.actor)
        self.assessment = set_assessment_status(self.assessment, 'open', self.actor)
        self.one, self.two = self.assessment.exam_sets.all()
        self.client.force_login(self.teacher.user)

    def url(self, exam_set):
        return reverse('academics:marks', args=[self.assessment.pk]) + f'?assignment={self.assignment.pk}&exam_set={exam_set.pk}'

    def enter(self, exam_set, score='', absent=False, action='save'):
        page = self.client.get(self.url(exam_set))
        row = page.context['rows'][0]
        control = page.context['control'].initial
        data = {'action': action, 'roster': control['roster'], 'revision': control['revision'],
                f'{row.prefix}-score': score, f'{row.prefix}-expected_revision': row.initial['expected_revision']}
        if absent:
            data[f'{row.prefix}-is_absent'] = 'on'
        return self.client.post(self.url(exam_set), data)

    def report(self):
        self.assessment = set_assessment_status(self.assessment, 'closed', self.actor)
        return generate_reports(self.assessment, self.actor)[0]

    def test_two_sheets_and_final_report_exclude_midterm(self):
        self.assertTrue(self.assessment.two_exam_sets)
        self.assertEqual(self.enter(self.one, 80).status_code, 302)
        self.assertEqual(self.enter(self.two, 70).status_code, 302)
        self.assertEqual(self.assessment.marks.count(), 2)
        self.assertEqual(self.midterm.marks.count(), 1)
        report = self.report()
        self.assertEqual(Decimal(report.snapshot['subjects'][0]['score']), Decimal('75'))
        self.assertEqual(report.snapshot['aggregate'], 1)
        self.assertEqual([Decimal(item['score']) for item in report.snapshot['subjects'][0]['exam_sets']], [80, 70])
        self.client.force_login(self.actor)
        for name in ('detail', 'print'):
            response = self.client.get(reverse(f'reports:{name}', args=[report.pk]))
            self.assertContains(response, 'Set One')
            self.assertContains(response, 'Set Two')
            self.assertNotContains(response, 'Mid-Term')
        self.assertTrue(report_pdf(report).startswith(b'%PDF'))

    def test_missing_set_blocks_close_and_forged_closed_report(self):
        self.enter(self.one, 80)
        with self.assertRaises(ValidationError):
            set_assessment_status(self.assessment, 'closed', self.actor)
        type(self.assessment).objects.filter(pk=self.assessment.pk).update(status='closed')
        with self.assertRaises(ValidationError):
            generate_reports(self.assessment, self.actor)

    def test_absent_set_is_not_zero_or_a_ranked_result(self):
        self.enter(self.one, 80)
        self.enter(self.two, absent=True)
        report = self.report()
        self.assertTrue(report.snapshot['has_absences'])
        self.assertIsNone(report.snapshot['average'])
        self.assertIsNone(report.snapshot['position'])
        self.assertTrue(report.snapshot['subjects'][0]['exam_sets'][1]['absent'])

    def test_configured_weights_and_immutable_configuration(self):
        self.assessment.set_one_weight = Decimal('40')
        self.assessment.full_clean()
        self.assessment.save()
        self.enter(self.one, 80)
        self.enter(self.two, 70)
        self.assessment.set_one_weight = Decimal('60')
        with self.assertRaises(ValidationError):
            self.assessment.full_clean()
        self.assessment.refresh_from_db()
        report = self.report()
        self.assertEqual(Decimal(report.snapshot['average']), Decimal('74'))
        snapshot = deepcopy(report.snapshot)
        begin_correction(self.assessment, 'Correct Set Two', self.actor)
        self.enter(self.two, 90)
        report.refresh_from_db()
        self.assertEqual(report.snapshot, snapshot)
        self.assertEqual(Decimal(self.report().snapshot['average']), Decimal('86'))

    def test_cross_set_token_and_wrong_assessment_set_rejected(self):
        page = self.client.get(self.url(self.one))
        control = page.context['control'].initial
        prefix = page.context['rows'][0].prefix
        data = {'action': 'save', 'roster': control['roster'], 'revision': 0, f'{prefix}-score': 90, f'{prefix}-expected_revision': 0}
        self.assertEqual(self.client.post(self.url(self.two), data).status_code, 200)
        self.assertFalse(self.assessment.marks.exists())
        url = reverse('academics:marks', args=[self.midterm.pk]) + f'?exam_set={self.one.pk}'
        self.assertEqual(self.client.get(url).status_code, 404)
        form = MarkForm({'score': 50, 'expected_revision': 0}, assessment=self.assessment, enrollment=self.enrollment, subject=self.subject, assignment=self.assignment)
        self.assertFalse(form.is_valid())

    def test_review_is_per_set_and_both_approvals_are_required(self):
        self.assessment.requires_mark_review = True
        self.assessment.save()
        self.enter(self.one, 80, action='submit')
        self.enter(self.two, 70, action='submit')
        self.client.force_login(self.users[User.Role.HEADTEACHER])
        for exam_set in (self.one, self.two):
            submission = MarkSubmission.objects.get(assessment=self.assessment, exam_set=exam_set)
            self.assertEqual(self.client.post(self.url(exam_set), {'review-action': 'approve', 'review-note': '', 'review-revision': submission.revision}).status_code, 302)
            if exam_set == self.one:
                with self.assertRaises(ValidationError):
                    set_assessment_status(self.assessment, 'closed', self.actor)
        self.assertEqual(Decimal(self.report().snapshot['average']), Decimal('75'))

    def test_invalid_weights_and_descriptive_averaging_rejected(self):
        for weight in (0, 100, -1, 101):
            self.assessment.set_one_weight = Decimal(weight)
            with self.assertRaises(ValidationError):
                self.assessment.full_clean()
        self.assessment.set_one_weight = Decimal(50)
        self.scheme.mode = 'descriptive'
        self.scheme.save()
        self.assessment.grading_scheme = self.scheme
        with self.assertRaisesMessage(ValidationError, 'numeric grading'):
            self.assessment.full_clean()

    def test_single_mark_endpoint_keeps_sets_separate(self):
        for exam_set, score in ((self.one, 60), (self.two, 90)):
            url = reverse('academics:mark_form', args=[self.assessment.pk, self.subject.pk, self.enrollment.pk]) + f'?exam_set={exam_set.pk}'
            response = self.client.post(url, {'score': score, 'expected_revision': 0})
            self.assertEqual(response.status_code, 302)
            self.assertIn(f'exam_set={exam_set.pk}', response.url)
        self.assertEqual(Decimal(self.report().snapshot['average']), Decimal(75))
