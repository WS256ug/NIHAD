from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.core.management import call_command, CommandError

from apps.academics.grading import grade_score
from apps.academics.models import GradingScheme
from tests.test_grading import GradingTestCase


class GradeCorrectionTests(GradingTestCase):
    def run_correction(self, **kwargs):
        return call_command('correct_assessment_grades', assessment=self.assessment.pk,
                            expected_scheme=self.scheme.pk, actor=self.actor.username,
                            rules=str(Path(__file__).resolve().parents[1] / 'deployment/nihad_grade_bands.json'),
                            stdout=StringIO(), **kwargs)

    def test_preview_rolls_back_and_apply_preserves_marks_and_old_rules(self):
        mark = self.mark('55')
        count, logs = GradingScheme.objects.count(), LogEntry.objects.count()
        self.run_correction()
        self.assertEqual(GradingScheme.objects.count(), count)
        self.assertEqual(LogEntry.objects.count(), logs)
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.grading_scheme_id, self.scheme.pk)
        self.run_correction(apply=True)
        self.assessment.refresh_from_db()
        mark.refresh_from_db()
        self.assertEqual(str(mark.score), '55.00')
        self.assertNotEqual(self.assessment.grading_scheme_id, self.scheme.pk)
        self.assertEqual(self.scheme.rules.count(), 2)
        rules = list(self.assessment.grading_scheme.rules.all())
        from decimal import Decimal
        for score, label in [('0', 'F9'), ('39.99', 'F9'), ('44', 'P8'), ('45', 'P7'),
                             ('55', 'C6'), ('60', 'C5'), ('66', 'C4'), ('77', 'C3'),
                             ('88', 'D2'), ('90', 'D1'), ('100', 'D1')]:
            self.assertEqual(grade_score(Decimal(score), Decimal(100), rules)[1].label, label)
        with self.assertRaises(CommandError):
            self.run_correction(apply=True)

    def test_rejects_closed_assessment_and_non_admin(self):
        with self.assertRaises(CommandError):
            call_command('correct_assessment_grades', assessment=self.assessment.pk,
                         expected_scheme=self.scheme.pk, actor=self.teacher.user.username,
                         rules='unused', stdout=StringIO())
        self.assessment.status = 'closed'
        self.assessment.save()
        with self.assertRaises(CommandError):
            self.run_correction(apply=True)

    def test_reports_prevent_correction(self):
        from apps.reports.models import StudentReport
        StudentReport.objects.create(assessment=self.assessment, enrollment=self.enrollment)
        with self.assertRaises(CommandError):
            self.run_correction(apply=True)

    def test_failure_rolls_back_created_version(self):
        count = GradingScheme.objects.count()
        with patch('apps.academics.management.commands.correct_assessment_grades.LogEntry.objects.create',
                   side_effect=ValueError('audit failed')):
            with self.assertRaises(CommandError):
                self.run_correction(apply=True)
        self.assertEqual(GradingScheme.objects.count(), count)
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.grading_scheme_id, self.scheme.pk)

class MissingGradeSchemeTests(GradingTestCase):
    def setUp(self):
        super().setUp()
        from apps.schools.models import Section
        from apps.academics.models import GradeRule, DivisionRule
        section = Section.objects.create(school=self.school, name='Source section')
        self.source = GradingScheme.objects.create(section=section, name='Source primary bands', aggregate_mode='all', is_active=True)
        for rule in self.scheme.rules.all():
            GradeRule.objects.create(scheme=self.source, label=rule.label, minimum=rule.minimum, maximum=rule.maximum, points=rule.points, sort_order=rule.sort_order)
        DivisionRule.objects.create(scheme=self.source, label='I', minimum=1, maximum=4)
        self.saved_mark = self.mark('98')
        self.assessment.grading_scheme = None
        self.assessment.save()

    def run_copy(self, **kwargs):
        call_command('correct_assessment_grades', assessment=self.assessment.pk,
                     expected_scheme=0, source_scheme=self.source.pk, actor=self.actor.username,
                     stdout=StringIO(), **kwargs)

    def test_copy_into_target_section_preserves_marks_and_preview_rolls_back(self):
        before = GradingScheme.objects.count()
        self.run_copy()
        self.assertEqual(GradingScheme.objects.count(), before)
        self.assessment.refresh_from_db()
        self.assertIsNone(self.assessment.grading_scheme_id)
        self.run_copy(apply=True)
        self.assessment.refresh_from_db()
        self.saved_mark.refresh_from_db()
        self.assertEqual(str(self.saved_mark.score), '98.00')
        target = self.assessment.grading_scheme
        self.assertEqual(target.section_id, self.assessment.academic_class.section_id)
        self.assertNotEqual(target.pk, self.source.pk)
        fields = ('label', 'minimum', 'maximum', 'points')
        self.assertEqual(list(target.rules.order_by('minimum').values(*fields)), list(self.source.rules.order_by('minimum').values(*fields)))
        self.assertEqual(target.divisions.count(), 1)
        from decimal import Decimal
        self.assertEqual(grade_score(Decimal('98'), Decimal('100'), target.rules.all())[1].label, 'Excellent')
        with self.assertRaises(CommandError):
            self.run_copy(apply=True)

    def test_invalid_or_inactive_source_rejected_without_linking(self):
        self.source.is_active = False
        self.source.save()
        with self.assertRaises(CommandError):
            self.run_copy(apply=True)
        self.assessment.refresh_from_db()
        self.assertIsNone(self.assessment.grading_scheme_id)

    def test_cross_section_required_subjects_are_not_silently_reassigned(self):
        from apps.academics.models import Subject
        subject = Subject.objects.create(section=self.source.section, code='REQ', name='Required')
        self.source.required_subjects.add(subject)
        with self.assertRaisesMessage(CommandError, 'required subjects'):
            self.run_copy(apply=True)

    def test_existing_reports_prevent_missing_scheme_repair(self):
        from apps.reports.models import StudentReport
        StudentReport.objects.create(assessment=self.assessment, enrollment=self.enrollment)
        with self.assertRaises(CommandError):
            self.run_copy(apply=True)
