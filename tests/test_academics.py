from datetime import date
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.academics.forms import ClassTeacherAssignmentForm, SubjectForm, TeacherForm, TeachingAssignmentForm
from apps.academics.models import ClassTeacherAssignment, Subject, Teacher, TeachingAssignment
from apps.academics.permissions import visible_enrollments
from apps.academics.services import save_academic, set_academic_active
from apps.schools.services import set_record_active
from apps.students.models import Enrollment
from tests.test_students import StudentTestCase


class AcademicTestCase(StudentTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.teacher = Teacher.objects.create(school=cls.school, user=cls.users[User.Role.TEACHER], phone="0700", date_joined=date(2025, 1, 1))
        cls.subject = Subject.objects.create(section=cls.primary, name="English", code="ENG")

    def assignment_data(self, **changes):
        return {"teacher": self.teacher.pk, "academic_year": self.year.pk, "term": self.term.pk, "academic_class": self.academic_class.pk, "stream": "", "subject": self.subject.pk, **changes}

    def assign(self, **changes):
        form = TeachingAssignmentForm(self.assignment_data(**changes), school=self.school, actor=self.actor)
        self.assertTrue(form.is_valid(), form.errors)
        return save_academic(form, self.actor)


class AcademicRecordTests(AcademicTestCase):
    def test_teacher_account_role_and_unique_profile(self):
        form = TeacherForm({"user": self.actor.pk, "phone": "0700", "date_joined": "2025-01-01", "employment_status": "active"}, school=self.school, actor=self.actor)
        self.assertFalse(form.is_valid())
        teacher_user = self.teacher.user
        teacher_user.role = User.Role.HEADTEACHER
        with self.assertRaisesMessage(ValidationError, "retain the Teacher role"):
            teacher_user.full_clean()

    def test_subject_is_unique_within_section(self):
        form = SubjectForm({"section": self.primary.pk, "name": "English", "code": "eng"}, school=self.school, actor=self.actor)
        self.assertFalse(form.is_valid())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Subject.objects.create(section=self.primary, name="Other", code="eng")

    def test_assignment_requires_matching_year_stream_and_subject_section(self):
        nursery_subject = Subject.objects.create(section=self.nursery, code="READ", name="Reading")
        for changes in ({"term": self.next_term.pk}, {"subject": nursery_subject.pk}, {"teacher": 9999}, {"stream": 9999}):
            form = TeachingAssignmentForm(self.assignment_data(**changes), school=self.school, actor=self.actor)
            self.assertFalse(form.is_valid())

    def test_whole_class_and_whole_year_assignments_cannot_overlap_specific_scope(self):
        assignment = self.assign(term="")
        form = TeachingAssignmentForm(self.assignment_data(stream=self.stream.pk), school=self.school, actor=self.actor)
        self.assertFalse(form.is_valid())
        set_academic_active(assignment, False, self.actor)
        self.assertTrue(TeachingAssignmentForm(self.assignment_data(stream=self.stream.pk), school=self.school, actor=self.actor).is_valid())

    def test_database_rejects_duplicate_nullable_scope(self):
        assignment = self.assign(term="", stream="")
        with self.assertRaises(IntegrityError), transaction.atomic():
            TeachingAssignment.objects.create(teacher=self.teacher, academic_year=self.year, academic_class=self.academic_class, section=self.primary, subject=self.subject)
        self.assertIsNone(assignment.term_id)

    def test_class_teacher_is_separate_and_scope_is_immutable(self):
        self.assign()
        form = ClassTeacherAssignmentForm(self.assignment_data(), school=self.school, actor=self.actor)
        self.assertTrue(form.is_valid(), form.errors)
        record = save_academic(form, self.actor)
        record.stream = self.stream
        with self.assertRaises(ValidationError):
            record.full_clean()
        self.assertEqual(ClassTeacherAssignment.objects.count(), 1)

    def test_deactivation_preserves_assignment_and_blocks_inactive_parents(self):
        assignment = self.assign(stream=self.stream.pk)
        for record in (self.subject, self.term, self.year, self.stream, self.academic_class):
            with self.subTest(record=record), self.assertRaises(ValidationError):
                if isinstance(record, Subject):
                    set_academic_active(record, False, self.actor)
                else:
                    set_record_active(record, False, self.actor)
        self.teacher.employment_status = "left"
        with self.assertRaises(ValidationError):
            self.teacher.full_clean()
        set_academic_active(assignment, False, self.actor)
        self.assertTrue(TeachingAssignment.objects.filter(pk=assignment.pk).exists())

    def test_audit_failure_rolls_back_and_service_checks_actor(self):
        form = TeachingAssignmentForm(self.assignment_data(), school=self.school, actor=self.actor)
        self.assertTrue(form.is_valid())
        with self.assertRaises(PermissionDenied):
            save_academic(form, self.teacher.user)
        with patch("apps.schools.services.LogEntry.objects.create", side_effect=RuntimeError("audit")):
            with self.assertRaises(RuntimeError):
                save_academic(form, self.actor)
        self.assertFalse(TeachingAssignment.objects.exists())


class AcademicAccessTests(AcademicTestCase):
    def test_teacher_can_only_read_assigned_students_and_enrollment_history(self):
        self.enroll()
        self.client.force_login(self.teacher.user)
        self.assertEqual(self.client.get(reverse("students:detail", args=[self.student.pk])).status_code, 404)
        self.assign()
        later = Enrollment.objects.create(student=self.student, academic_year=self.next_year, section=self.primary, academic_class=self.academic_class, enrollment_date=date(2027, 2, 1))
        self.assertEqual(visible_enrollments(self.teacher.user).count(), 1)
        response = self.client.get(reverse("students:detail", args=[self.student.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(later, response.context["enrollments"])
        self.assertEqual(response.context["guardian_links"], [])
        response = self.client.get(reverse("students:list"), {"year": self.next_year.pk})
        self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_assignment_revocation_removes_student_visibility(self):
        self.enroll()
        assignment = self.assign()
        self.assertEqual(visible_enrollments(self.teacher.user).count(), 1)
        set_academic_active(assignment, False, self.actor)
        self.assertFalse(visible_enrollments(self.teacher.user).exists())

    def test_role_matrix_crud_and_csrf(self):
        for role, user in self.users.items():
            self.client.force_login(user)
            reader = role in (User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER, User.Role.TEACHER)
            manager = role in (User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN)
            for kind in ("teachers", "subjects", "teaching", "class-teachers"):
                self.assertEqual(self.client.get(reverse("academics:record_list", args=[kind])).status_code, 200 if reader else 403)
                self.assertEqual(self.client.get(reverse("academics:record_create", args=[kind])).status_code, 200 if manager else 403)
                if not manager:
                    self.assertEqual(self.client.post(reverse("academics:record_create", args=[kind]), {}).status_code, 403)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        self.assertEqual(client.post(reverse("academics:record_create", args=["subjects"]), {}).status_code, 403)

    def test_teacher_lists_only_own_subjects_and_assignments(self):
        self.assign()
        Subject.objects.create(section=self.primary, code="MATH", name="Mathematics")
        self.client.force_login(self.teacher.user)
        response = self.client.get(reverse("academics:record_list", args=["subjects"]))
        self.assertContains(response, "English")
        self.assertNotContains(response, "Mathematics")
