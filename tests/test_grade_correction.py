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
