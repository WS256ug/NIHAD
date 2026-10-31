from django.core.exceptions import ValidationError
from django.urls import reverse
from apps.accounts.models import User
from apps.academics.forms import MarkForm
from apps.academics.models import GradeRule, GradingScheme, Mark
from apps.academics.services import save_mark, set_assessment_status
from apps.reports.services import generate_reports, review_report, publish_report, begin_correction
from apps.reports.pdf import report_pdf
from tests.test_reports import ReportTestCase


class NurseryProgressTests(ReportTestCase):
    def setUp(self):
        super().setUp()
        scheme = GradingScheme.objects.create(section=self.primary, name='Nursery progress', mode='descriptive', is_active=True)
        self.level = GradeRule.objects.create(scheme=scheme, label='Developing', sort_order=1)
        self.assessment.grading_scheme = scheme
        self.assessment.nursery_progress = True
        self.assessment.save()
        self.subject.illustration = 'numbers'
        self.subject.save()
        self.url = reverse('academics:marks', args=[self.assessment.pk]) + f'?assignment={self.assignment.pk}'
        self.client.force_login(self.teacher.user)

    def payload(self, observation='', action='save'):
        response = self.client.get(self.url)
        row = response.context['rows'][0]
        return {'roster': response.context['control'].initial['roster'],
                'revision': response.context['control'].initial['revision'], 'action': action,
                f'{row.prefix}-level': self.level.pk, f'{row.prefix}-observation': observation,
                f'{row.prefix}-expected_revision': row.initial['expected_revision']}

    def save_result(self, observation='Counts five objects independently.'):
        response = self.client.post(self.url, self.payload(observation))
        self.assertEqual(response.status_code, 302)
        return Mark.objects.get(assessment=self.assessment)

    def generate(self):
        self.save_result()
        self.assessment = set_assessment_status(self.assessment, 'closed', self.actor)
        return generate_reports(self.assessment, self.actor)[0]

    def test_draft_observation_required_at_close_and_generation(self):
        self.save_result('')
        with self.assertRaisesMessage(ValidationError, 'teacher observation'):
            set_assessment_status(self.assessment, 'closed', self.actor)
        self.assessment.status = 'closed'
        self.assessment.save()
        with self.assertRaises(ValidationError):
            generate_reports(self.assessment, self.actor)

    def test_observation_only_edit_is_saved_and_revision_checked(self):
        first = self.save_result()
        stale = self.payload('Stale observation')
        second = self.save_result('Counts six objects independently.')
        self.assertEqual(second.revision, first.revision + 1)
        self.assertEqual(second.observation, 'Counts six objects independently.')
        self.assertContains(self.client.post(self.url, stale), 'changed')

    def test_submit_without_observation_rolls_back(self):
        self.assessment.requires_mark_review = True
        self.assessment.save()
        response = self.client.post(self.url, self.payload('', 'submit'))
        self.assertContains(response, 'teacher observation')
        self.assertFalse(Mark.objects.filter(assessment=self.assessment).exists())

    def test_report_goes_to_headteacher_without_teacher_comment(self):
        report = self.generate()
        self.assertEqual(report.status, 'review')
        self.assertEqual(report.teacher_comment, '')
        self.assertIn('Developing: 1 learning area', report.headteacher_comment)
        self.assertEqual(report.snapshot['subjects'][0]['observation'], 'Counts five objects independently.')
        self.assertEqual(report.snapshot['subjects'][0]['illustration'], 'numbers')
        report = review_report(report, report.headteacher_comment, True, self.users[User.Role.HEADTEACHER])
        report = publish_report(report, self.actor)
        self.assertEqual(report.status, 'published')
        self.assertTrue(report_pdf(report).startswith(b'%PDF'))
        response = self.client.get(reverse('reports:detail', args=[report.pk]))
        self.assertContains(response, 'Counts five objects independently.')
        self.assertContains(response, 'nursery-picture-numbers')
        self.assertNotContains(response, 'Class-teacher comment')
        begin_correction(self.assessment, 'Correct observation', self.actor)
        self.assessment.refresh_from_db()
        self.save_result('Counts six objects independently.')
        report.refresh_from_db()
        self.assertEqual(report.snapshot['subjects'][0]['observation'], 'Counts five objects independently.')

    def test_observations_escape_html_and_unauthorized_teacher_cannot_edit(self):
        self.save_result('<script>alert(1)</script>')
        self.assertContains(self.client.get(self.url), '&lt;script&gt;')
        self.client.force_login(self.users[User.Role.BURSAR])
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_numeric_scheme_cannot_use_nursery_format(self):
        self.assessment.grading_scheme = self.scheme
        with self.assertRaisesMessage(ValidationError, 'descriptive'):
            self.assessment.full_clean()

    def test_setup_defaults_are_idempotent_and_preserve_section_grades(self):
        from django.core.management import call_command
        from apps.academics.section_grades import current_scheme
        from io import StringIO
        before = current_scheme(self.primary)
        for _ in range(2):
            call_command('setup_nursery_progress', section=self.primary.pk, actor=self.actor.pk, stdout=StringIO())
        self.assertEqual(current_scheme(self.primary), before)
        scheme = GradingScheme.objects.get(section=self.primary, nursery_only=True)
        self.assertEqual(scheme.rules.count(), 4)
        self.assertTrue(scheme.is_active)

    def test_exam_form_selects_nursery_scheme_without_changing_regular_exam_defaults(self):
        from apps.academics.forms import AssessmentForm
        from apps.academics.services import save_academic
        self.assessment.delete()
        data = {'assessment_type': self.assessment_type.pk, 'term': self.term.pk,
                'academic_class': self.academic_class.pk, 'date': '2026-03-01',
                'maximum_score': '100', 'nursery_progress': True,
                'nursery_scheme': self.level.scheme_id}
        form = AssessmentForm(data, school=self.school, actor=self.actor)
        self.assertTrue(form.is_valid(), form.errors)
        exam = save_academic(form, self.actor)
        self.assertTrue(exam.nursery_progress)
        self.assertEqual(exam.grading_scheme_id, self.level.scheme_id)
