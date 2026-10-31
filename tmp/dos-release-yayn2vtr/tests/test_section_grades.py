from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.accounts.models import User
from apps.academics.forms import AssessmentForm, SectionDivisionForm, SectionGradeForm
from apps.academics.models import Assessment, AssessmentType, GradeRule, GradingScheme
from apps.academics.section_grades import assessment_grades, current_rules, current_scheme, save_section_rule
from apps.academics.services import save_academic, set_assessment_status
from tests.test_grading import GradingTestCase
from tests.test_schools import SchoolTestCase


class SectionGradeSetupTests(SchoolTestCase):
    def grade(self, section=None, instance=None, **changes):
        data = {"section": (section or self.primary).pk, "label": "Excellent", "minimum": 0,
                "maximum": 100, "points": 1, "sort_order": 0, **changes}
        form = SectionGradeForm(data, school=self.school, actor=self.actor, instance=instance)
        self.assertTrue(form.is_valid(), form.errors)
        return save_section_rule(form, self.actor)

    def test_numeric_setup_automatically_becomes_ready_when_ranges_are_complete(self):
        self.grade(label="Developing", maximum=50, points=9)
        self.assertFalse(current_scheme(self.primary).is_active)
        with self.assertRaisesMessage(ValidationError, "Finish adding grades"):
            assessment_grades(self.primary)
        self.grade(minimum=50)
        self.assertTrue(assessment_grades(self.primary).is_active)
        self.assertEqual(GradingScheme.objects.count(), 1)

    def test_descriptive_levels_are_separate_and_need_no_scheme_selection(self):
        level = self.grade(section=self.nursery, minimum="", maximum="", points="", label="Achieved")
        self.assertEqual(level.scheme.mode, "descriptive")
        self.assertTrue(assessment_grades(self.nursery).is_active)
        self.grade()
        self.assertEqual(current_scheme(self.primary).mode, "numeric")
        with self.assertRaisesMessage(ValidationError, "same grade type"):
            self.grade(section=self.nursery)

    def test_bad_ranges_and_duplicates_do_not_replace_current_grades(self):
        first = self.grade()
        for changes in ({"label": "Overlap", "minimum": 50}, {"label": "Excellent"}):
            with self.assertRaises(ValidationError):
                self.grade(**changes)
        self.assertEqual(GradingScheme.objects.count(), 1)
        self.assertEqual(current_scheme(self.primary).pk, first.scheme_id)
        self.assertEqual(GradeRule.objects.count(), 1)

    def test_assessment_automatically_uses_class_section_and_ignores_forged_scheme(self):
        primary = self.grade()
        nursery = self.grade(section=self.nursery, label="Achieved", minimum="", maximum="", points="")
        assessment_type = AssessmentType.objects.create(school=self.school, name="Mid-Term")
        data = {"assessment_type": assessment_type.pk, "term": self.term.pk,
                "academic_class": self.academic_class.pk, "stream": "", "date": "2026-03-01",
                "maximum_score": 100, "grading_scheme": nursery.scheme_id}
        form = AssessmentForm(data, school=self.school, actor=self.actor)
        self.assertNotIn("grading_scheme", form.fields)
        self.assertTrue(form.is_valid(), form.errors)
        assessment = save_academic(form, self.actor)
        self.assertEqual(assessment.grading_scheme_id, primary.scheme_id)

    def test_divisions_use_section_and_require_grade_points(self):
        self.grade(points="")
        data = {"section": self.primary.pk, "label": "I", "minimum": 1, "maximum": 12}
        form = SectionDivisionForm(data, school=self.school, actor=self.actor)
        self.assertTrue(form.is_valid(), form.errors)
        with self.assertRaisesMessage(ValidationError, "points to every grade"):
            save_section_rule(form, self.actor)
        self.grade(instance=current_scheme(self.primary).rules.get(), points=1)
        record = save_section_rule(form, self.actor)
        self.assertEqual(record.scheme.aggregate_mode, "all")
        self.assertTrue(current_scheme(self.primary).is_active)

    def test_assessment_can_be_created_before_grades_are_complete(self):
        self.grade(label="Developing", maximum=50, points=9)
        assessment_type = AssessmentType.objects.create(school=self.school, name="Mid-Term")
        data = {"assessment_type": assessment_type.pk, "term": self.term.pk,
                "academic_class": self.academic_class.pk, "stream": "", "date": "2026-03-01",
                "maximum_score": 100}
        form = AssessmentForm(data, school=self.school, actor=self.actor)
        self.assertTrue(form.is_valid(), form.errors)
        assessment = save_academic(form, self.actor)
        self.assertIsNone(assessment.grading_scheme_id)
        self.assertEqual(assessment.status, "draft")
        self.grade(minimum=50)
        assessment = set_assessment_status(assessment, "open", self.actor)
        self.assertEqual(assessment.grading_scheme_id, current_scheme(self.primary).pk)

    def test_workspace_shows_grades_without_scheme_controls_and_checks_roles(self):
        self.client.force_login(self.actor)
        self.assertNotContains(self.client.get(reverse("academics:overview")), "Grading schemes")
        url = reverse("academics:record_create", args=["grade-rules"])
        response = self.client.get(url)
        self.assertContains(response, 'name="section"')
        self.assertNotContains(response, 'name="scheme"')
        self.assertNotContains(response, 'name="aggregate_mode"')
        self.client.force_login(self.users[User.Role.TEACHER])
        self.assertEqual(self.client.post(url, {}).status_code, 403)


class HistoricalSectionGradeTests(GradingTestCase):
    def edited_form(self, **changes):
        form = SectionGradeForm({"section": self.primary.pk, "label": "Excellent", "minimum": 50,
                                 "maximum": 100, "points": 2, "sort_order": 0, **changes},
                                instance=self.high, school=self.school, actor=self.actor)
        self.assertTrue(form.is_valid(), form.errors)
        return form

    def test_used_grades_are_versioned_and_existing_assessment_keeps_original(self):
        self.mark()
        old_id = self.scheme.pk
        saved = save_section_rule(self.edited_form(), self.actor)
        self.assertNotEqual(saved.scheme_id, old_id)
        self.high.refresh_from_db()
        self.assessment.refresh_from_db()
        self.assertEqual(self.high.points, 1)
        self.assertEqual(self.assessment.grading_scheme_id, old_id)
        self.assertEqual(current_scheme(self.primary).pk, saved.scheme_id)
        self.assertEqual(saved.scheme.divisions.count(), self.scheme.divisions.count())
        self.assertEqual(saved.scheme.aggregate_mode, self.scheme.aggregate_mode)
        self.assertEqual(current_rules(GradeRule.objects.all()).count(), 2)
        form = AssessmentForm({"date": "2026-03-01", "maximum_score": 100}, instance=self.assessment,
                              school=self.school, actor=self.actor)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(save_academic(form, self.actor).grading_scheme_id, old_id)
        with self.assertRaisesMessage(ValidationError, "grades have changed"):
            save_section_rule(self.edited_form(), self.actor)

    def test_version_creation_rolls_back_when_audit_fails(self):
        before = GradingScheme.objects.count()
        with patch("apps.schools.services.LogEntry.objects.create", side_effect=RuntimeError("audit")):
            with self.assertRaises(RuntimeError):
                save_section_rule(self.edited_form(), self.actor)
        self.assertEqual(GradingScheme.objects.count(), before)
        self.high.refresh_from_db()
        self.assertEqual(self.high.points, 1)
