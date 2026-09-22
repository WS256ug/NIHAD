from decimal import Decimal
from types import SimpleNamespace
from django.core.exceptions import ValidationError
from django.urls import reverse
from apps.academics.forms import GradingSchemeForm, MarkForm
from apps.academics.grading import calculate_results, competition_positions, grade_score
from apps.academics.models import DivisionRule, GradeRule, GradingScheme, Subject
from apps.academics.services import save_academic, save_mark, set_academic_active
from tests.test_assessments import AssessmentTestCase


class GradingTestCase(AssessmentTestCase):
    def setUp(self):
        super().setUp()
        self.scheme = GradingScheme.objects.create(section=self.primary, name='Primary v1', aggregate_mode='all')
        self.low = GradeRule.objects.create(scheme=self.scheme, label='Developing', minimum=0, maximum=50, points=9)
        self.high = GradeRule.objects.create(scheme=self.scheme, label='Excellent', minimum=50, maximum=100, points=1)
        DivisionRule.objects.create(scheme=self.scheme, label='I', minimum=1, maximum=4)
        self.scheme = set_academic_active(self.scheme, True, self.actor)
        self.assessment.grading_scheme = self.scheme
        self.assessment.save()


class GradingTests(GradingTestCase):
    def test_boundaries_and_non_100_maximum_use_exact_percentages(self):
        for score, expected in [('0', self.low), ('49.99', self.low), ('50', self.high), ('100', self.high)]:
            percentage, rule = grade_score(Decimal(score), Decimal('100'), [self.low, self.high])
            self.assertEqual(rule.pk, expected.pk)
        self.assertEqual(grade_score(Decimal('25'), Decimal('50'), [self.low, self.high])[1].pk, self.high.pk)

    def test_result_aggregate_division_and_average(self):
        mark = self.mark('82.25')
        result = calculate_results(self.scheme, [mark], self.assessment.maximum_score)
        self.assertEqual((result['total'], result['average'], result['aggregate'], result['division']), ('82.25', '82.25', 1, 'I'))

    def test_gaps_and_overlapping_grade_ranges_are_rejected(self):
        scheme = GradingScheme.objects.create(section=self.primary, name='Gap')
        GradeRule.objects.create(scheme=scheme, label='A', minimum=10, maximum=100)
        with self.assertRaisesMessage(ValidationError, 'gaps or overlaps'):
            set_academic_active(scheme, True, self.actor)
        rule = GradeRule(scheme=scheme, label='B', minimum=0, maximum=50)
        with self.assertRaisesMessage(ValidationError, 'overlaps'):
            rule.full_clean()

    def test_best_n_keeps_required_subject_even_with_weaker_grade(self):
        self.scheme.is_active = False
        self.scheme.aggregate_mode = 'best'
        self.scheme.best_n = 2
        self.scheme.save()
        self.scheme.required_subjects.add(self.subject)
        math = Subject.objects.create(section=self.primary, name='Math', code='MATH')
        science = Subject.objects.create(section=self.primary, name='Science', code='SCI')
        marks = [SimpleNamespace(subject_id=s.pk, subject=s, score=Decimal(score)) for s, score in [(self.subject, '20'), (math, '90'), (science, '80')]]
        self.scheme = set_academic_active(self.scheme, True, self.actor)
        result = calculate_results(self.scheme, marks, Decimal('100'))
        self.assertEqual(result['aggregate'], 10)
        self.assertEqual(result['aggregate_subjects'], [self.subject.pk, math.pk])
        with self.assertRaisesMessage(ValidationError, 'required aggregate'):
            calculate_results(self.scheme, marks[1:], Decimal('100'))

    def test_used_scheme_and_rules_cannot_change(self):
        self.mark()
        with self.assertRaises(ValidationError):
            set_academic_active(self.scheme, False, self.actor)
        self.high.points = 2
        with self.assertRaisesMessage(ValidationError, 'already used'):
            self.high.full_clean()
        form = GradingSchemeForm({'section': self.primary.pk, 'name': 'Changed', 'mode': 'numeric', 'aggregate_mode': 'all'}, instance=self.scheme, school=self.school, actor=self.actor)
        self.assertFalse(form.is_valid())

    def test_tied_positions_use_competition_ranking(self):
        self.assertEqual(competition_positions({4: {'average': '80.00'}, 2: {'average': '90.00'}, 1: {'average': '80.00'}, 3: {'average': '60.00'}}), {2: 1, 1: 2, 4: 2, 3: 4})

    def test_descriptive_learning_levels_have_no_numeric_summary(self):
        scheme = GradingScheme.objects.create(section=self.primary, name='Early learning', mode='descriptive')
        level = GradeRule.objects.create(scheme=scheme, label='Achieved')
        scheme = set_academic_active(scheme, True, self.actor)
        self.assessment.grading_scheme = scheme
        self.assessment.save()
        form = MarkForm({'level': level.pk, 'expected_revision': 0}, assessment=self.assessment, enrollment=self.enrollment, subject=self.subject, assignment=self.assignment)
        self.assertTrue(form.is_valid(), form.errors)
        mark = save_mark(form, self.teacher.user)
        result = calculate_results(scheme, [mark], Decimal('100'))
        self.assertEqual(result['subjects'][0]['grade'], 'Achieved')
        self.assertIsNone(result['average'])
        self.assertIsNone(result['aggregate'])
        self.client.force_login(self.teacher.user)
        self.assertContains(self.client.get(reverse('academics:marks', args=[self.assessment.pk])), 'Achieved')

    def test_grading_configuration_pages_and_required_subject_scope(self):
        self.client.force_login(self.actor)
        for kind in ('grading-schemes', 'grade-rules', 'division-rules'):
            self.assertEqual(self.client.get(reverse('academics:record_create', args=[kind])).status_code, 200)
            self.assertEqual(self.client.get(reverse('academics:record_list', args=[kind])).status_code, 200)
        form = GradingSchemeForm({'section': self.nursery.pk, 'name': 'Nursery', 'mode': 'numeric', 'aggregate_mode': 'selected', 'required_subjects': [self.subject.pk]}, school=self.school, actor=self.actor)
        self.assertFalse(form.is_valid())
