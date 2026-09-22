from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from django.contrib.admin.models import LogEntry
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client
from django.urls import reverse

from apps.accounts.forms import ManagedAccountChangeForm
from apps.accounts.models import User
from apps.schools.models import AcademicClass, Section, Stream
from apps.schools.services import set_record_active
from apps.students import services
from apps.students.forms import EnrollmentForm, GuardianForm, GuardianLinkForm, StudentForm, StudentRegistrationForm
from apps.students.models import Enrollment, Guardian, Student, StudentGuardian, StudentNumber
from apps.students.permissions import visible_students
from tests.test_schools import SchoolTestCase


class StudentTestCase(SchoolTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.student = Student.objects.create(school=cls.school, student_id="STD-000001", first_name="Mary", last_name="Wasswa", gender="female", date_of_birth=date(2018, 5, 1), admission_date=date(2025, 1, 1))
        StudentNumber.objects.create(school=cls.school, last_value=1)
        cls.guardian = Guardian.objects.create(school=cls.school, first_name="Jane", last_name="Wasswa", email="jane@example.test", phone="0700000000")

    def student_data(self, **changes):
        return {"first_name": "Sarah", "middle_name": "", "last_name": "Wasswa", "gender": "female", "date_of_birth": "2019-01-01", "admission_date": "2025-01-01", "admission_number": "", "existing_guardian": self.guardian.pk, "relationship": "Mother", **changes}

    def enrollment_data(self, **changes):
        return {"academic_year": self.year.pk, "academic_class": self.academic_class.pk, "stream": "", "enrollment_date": "2026-01-02", "status": "current", "completion_date": "", **changes}

    def enroll(self, **changes):
        form = EnrollmentForm(self.enrollment_data(**changes), student=self.student)
        self.assertTrue(form.is_valid(), form.errors)
        return services.enroll_student(form, self.actor)

    def link(self, **changes):
        form = GuardianLinkForm({"guardian": self.guardian.pk, "relationship": "Mother", **changes}, student=self.student)
        self.assertTrue(form.is_valid(), form.errors)
        return services.save_link(form, self.actor)



class StudentRecordTests(StudentTestCase):
    def test_ids_are_generated_unique_immutable_and_not_taken_from_post(self):
        for expected in ("STD-000002", "STD-000003"):
            form = StudentRegistrationForm(self.student_data(student_id="FORGED", school="999", status="graduated", created_by="999"), school=self.school)
            self.assertTrue(form.is_valid(), form.errors)
            student = services.save_student(form, self.actor)
            self.assertEqual(student.student_id, expected)
            self.assertEqual(student.status, Student.Status.ACTIVE)
            self.assertEqual(student.created_by, self.actor)
        student.student_id = "FORGED"
        with self.assertRaisesMessage(ValidationError, "cannot be reassigned"):
            student.full_clean()
        self.assertEqual(Student.objects.values("student_id").distinct().count(), 3)

    def test_registration_audit_failure_rolls_back_student_and_sequence(self):
        form = StudentRegistrationForm(self.student_data(), school=self.school)
        self.assertTrue(form.is_valid(), form.errors)
        with patch("apps.schools.services.LogEntry.objects.create", side_effect=RuntimeError("audit failed")):
            with self.assertRaises(RuntimeError):
                services.save_student(form, self.actor)
        self.assertEqual(Student.objects.count(), 1)
        self.assertEqual(StudentNumber.objects.get(pk=self.school.pk).last_value, 1)

    def test_admission_number_case_insensitive_uniqueness_allows_empty_values(self):
        self.student.admission_number = "A-123"
        self.student.save()
        form = StudentForm(self.student_data(admission_number=" a-123 "), school=self.school)
        self.assertFalse(form.is_valid())
        self.assertIn("already in use", str(form.errors))
        with self.assertRaises(IntegrityError), transaction.atomic():
            Student.objects.create(school=self.school, student_id="STD-OTHER", first_name="Jane", last_name="Doe", date_of_birth=date(2010, 1, 1), admission_date=date(2025, 1, 1), admission_number="a-123")

    def test_names_and_birth_admission_dates_are_validated(self):
        for changes in ({"first_name": " "}, {"date_of_birth": "2026-01-01"}, {"admission_date": "2999-01-01"}, {"gender": "invalid"}):
            with self.subTest(changes=changes):
                form = StudentForm(self.student_data(**changes), school=self.school)
                self.assertFalse(form.is_valid())

    def test_database_rejects_bad_student_dates_status_gender_and_duplicate_id(self):
        for fields in ({"date_of_birth": date(2030, 1, 1)}, {"status": "unknown"}, {"gender": "unknown"}, {"student_id": ""}):
            with self.subTest(fields=fields), self.assertRaises(IntegrityError), transaction.atomic():
                Student.objects.filter(pk=self.student.pk).update(**fields)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Student.objects.create(school=self.school, student_id=self.student.student_id, first_name="John", last_name="Doe", date_of_birth=date(2010, 1, 1), admission_date=date(2025, 1, 1))

    def test_stale_profile_does_not_overwrite_new_status(self):
        form = StudentForm(self.student_data(), instance=self.student, school=self.school)
        self.assertTrue(form.is_valid(), form.errors)
        services.set_student_status(self.student, "inactive", self.actor)
        updated = services.save_student(form, self.actor)
        self.assertEqual(updated.status, "inactive")
        self.assertEqual(updated.student_id, "STD-000001")

    def test_student_cannot_leave_with_open_enrollment_and_admission_cannot_pass_history(self):
        enrollment = self.enroll()
        with self.assertRaisesMessage(ValidationError, "Close current enrollments"):
            services.set_student_status(self.student, "withdrawn", self.actor)
        self.student.admission_date = date(2026, 2, 1)
        with self.assertRaisesMessage(ValidationError, "later than an existing enrollment"):
            self.student.full_clean()
        services.close_enrollment(enrollment, "withdrawn", date(2026, 3, 1), self.actor)
        updated = services.set_student_status(self.student, "withdrawn", self.actor)
        self.assertEqual(updated.status, "withdrawn")
        form = EnrollmentForm(self.enrollment_data(enrollment_date="2026-03-02"), student=updated)
        self.assertFalse(form.is_valid())


class GuardianRecordTests(StudentTestCase):
    def test_registration_captures_guardian_without_creating_an_account(self):
        before = User.objects.count()
        form = StudentRegistrationForm(self.student_data(existing_guardian="", guardian_first_name="Alice", guardian_last_name="Doe", guardian_phone="0700", guardian_email="alice@example.test"), school=self.school)
        self.assertTrue(form.is_valid(), form.errors)
        student = services.save_student(form, self.actor)
        link = student.guardian_links.get()
        self.assertEqual(str(link.guardian), "Alice Doe")
        self.assertTrue(link.is_primary)
        self.assertEqual(User.objects.count(), before)

    def test_registration_requires_guardian_details_or_existing_contact(self):
        form = StudentRegistrationForm(self.student_data(existing_guardian=""), school=self.school)
        self.assertFalse(form.is_valid())
        self.assertIn("guardian_phone", form.errors)

    def test_existing_contact_can_link_siblings_without_duplicate_contacts(self):
        self.link(is_primary="on")
        form = StudentRegistrationForm(self.student_data(), school=self.school)
        self.assertTrue(form.is_valid(), form.errors)
        student = services.save_student(form, self.actor)
        self.assertEqual(student.guardian_links.get().guardian, self.guardian)
        self.assertEqual(self.guardian.student_links.count(), 2)
        self.assertEqual(Guardian.objects.count(), 1)

    def test_contact_edit_preserves_relationships(self):
        link = self.link()
        form = GuardianForm({"first_name": "Jane", "last_name": "Updated", "phone": "0777", "email": "jane@example.test"}, instance=self.guardian, school=self.school)
        self.assertTrue(form.is_valid(), form.errors)
        services.save_guardian(form, self.actor)
        link.refresh_from_db()
        self.assertEqual(str(link.guardian), "Jane Updated")
        with self.assertRaises(ProtectedError):
            self.guardian.delete()

    def test_multiple_guardians_one_primary_and_reactivation(self):
        link = self.link(is_primary="on", is_emergency_contact="on")
        guardian = Guardian.objects.create(school=self.school, first_name="John", last_name="Wasswa", phone="0777")
        form = GuardianLinkForm({"guardian": guardian.pk, "relationship": "Father", "is_primary": "on"}, student=self.student)
        self.assertFalse(form.is_valid())
        with self.assertRaises(IntegrityError), transaction.atomic():
            StudentGuardian.objects.create(student=self.student, guardian=guardian, relationship="Father", is_primary=True)
        services.set_link_active(link, False, self.actor)
        link.refresh_from_db()
        self.assertFalse(link.is_primary or link.is_emergency_contact or link.is_active)
        self.assertTrue(services.set_link_active(link, True, self.actor).is_active)

    def test_duplicate_link_is_rejected_and_history_protected(self):
        self.link()
        form = GuardianLinkForm({"guardian": self.guardian.pk, "relationship": "Mother"}, student=self.student)
        self.assertFalse(form.is_valid())
        with self.assertRaises(ProtectedError):
            self.student.delete()


class EnrollmentRecordTests(StudentTestCase):
    def test_optional_stream_and_history_survive_next_year_enrollment(self):
        old = self.enroll()
        self.assertIsNone(old.stream)
        services.close_enrollment(old, "promoted", date(2026, 12, 31), self.actor)
        next_class = AcademicClass.objects.create(section=self.primary, name="P.2")
        newer = self.enroll(academic_year=self.next_year.pk, academic_class=next_class.pk, enrollment_date="2027-01-02")
        old.refresh_from_db()
        self.assertEqual(old.academic_class_id, self.academic_class.pk)
        self.assertEqual(old.status, "promoted")
        self.assertEqual(newer.academic_class, next_class)
        self.assertEqual(self.student.enrollments.count(), 2)

    def test_same_year_class_change_requires_nonoverlapping_closed_record(self):
        old = self.enroll()
        form = EnrollmentForm(self.enrollment_data(enrollment_date="2026-06-01"), student=self.student)
        self.assertFalse(form.is_valid())
        services.close_enrollment(old, "completed", date(2026, 5, 31), self.actor)
        form = EnrollmentForm(self.enrollment_data(enrollment_date="2026-05-31"), student=self.student)
        self.assertFalse(form.is_valid())
        current = self.enroll(enrollment_date="2026-06-01", stream=self.stream.pk)
        self.assertEqual(current.stream, self.stream)

    def test_dates_status_and_stream_must_match_context(self):
        other_class = AcademicClass.objects.create(section=self.nursery, name="Top")
        wrong_stream = Stream.objects.create(academic_class=other_class, name="West")
        cases = [
            {"stream": wrong_stream.pk}, {"enrollment_date": "2025-12-31"},
            {"enrollment_date": "2027-01-01"}, {"status": "completed"},
            {"status": "completed", "completion_date": "2026-01-01"},
            {"status": "completed", "completion_date": "2027-01-01"},
            {"completion_date": "2026-05-01"}, {"status": "bad"},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                form = EnrollmentForm(self.enrollment_data(**changes), student=self.student)
                self.assertFalse(form.is_valid())

    def test_immutable_context_and_closed_history(self):
        record = self.enroll()
        for field, value in [("enrollment_date", date(2026, 2, 1)), ("stream_id", self.stream.pk), ("academic_year_id", self.next_year.pk), ("section_id", self.nursery.pk)]:
            record.refresh_from_db()
            setattr(record, field, value)
            with self.subTest(field=field), self.assertRaisesMessage(ValidationError, "cannot be reassigned"):
                record.full_clean()
        record.refresh_from_db()
        closed = services.close_enrollment(record, "completed", date(2026, 4, 1), self.actor)
        closed.completion_date = date(2026, 4, 2)
        with self.assertRaisesMessage(ValidationError, "cannot be changed"):
            closed.full_clean()
        with self.assertRaisesMessage(ValidationError, "already closed"):
            services.close_enrollment(record, "completed", date(2026, 5, 1), self.actor)

    def test_database_current_uniqueness_and_closure_checks(self):
        record = self.enroll()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Enrollment.objects.create(student=self.student, academic_year=self.year, section=self.primary, academic_class=self.academic_class, enrollment_date=date(2026, 6, 1))
        for fields in ({"status": "completed"}, {"completion_date": date(2026, 5, 1)}, {"status": "bad", "completion_date": date(2026, 5, 1)}, {"status": "completed", "completion_date": date(2026, 1, 1)}):
            with self.subTest(fields=fields), self.assertRaises(IntegrityError), transaction.atomic():
                Enrollment.objects.filter(pk=record.pk).update(**fields)

    def test_enrollment_prevents_parent_deactivation_and_year_shrinking(self):
        self.enroll(stream=self.stream.pk)
        for record in (self.stream, self.academic_class, self.primary, self.year):
            with self.subTest(record=record), self.assertRaises(ValidationError):
                set_record_active(record, False, self.actor)
        self.year.start_date = date(2026, 1, 3)
        with self.assertRaisesMessage(ValidationError, "existing enrollment dates"):
            self.year.full_clean()

    def test_historical_dates_still_protect_year_after_closure(self):
        self.enroll(status="completed", completion_date="2026-12-31")
        self.year.end_date = date(2026, 12, 30)
        with self.assertRaisesMessage(ValidationError, "existing enrollment dates"):
            self.year.full_clean()
        for record in (self.student, self.academic_class, self.year):
            with self.subTest(record=record), self.assertRaises(ProtectedError):
                record.delete()

    def test_stale_form_rechecks_parent_and_student_after_lock(self):
        form = EnrollmentForm(self.enrollment_data(), student=self.student)
        self.assertTrue(form.is_valid())
        AcademicClass.objects.filter(pk=self.academic_class.pk).update(is_active=False)
        with self.assertRaisesMessage(ValidationError, "active year, section, class"):
            services.enroll_student(form, self.actor)
        self.assertFalse(Enrollment.objects.exists())


    def test_audit_failure_rolls_back_enrollment(self):
        form = EnrollmentForm(self.enrollment_data(), student=self.student)
        self.assertTrue(form.is_valid())
        with patch("apps.schools.services.LogEntry.objects.create", side_effect=RuntimeError("failed")):
            with self.assertRaises(RuntimeError):
                services.enroll_student(form, self.actor)
        self.assertFalse(Enrollment.objects.exists())


class StudentViewTests(StudentTestCase):
    def test_role_matrix_for_all_pages_and_writes(self):
        enrollment = self.enroll()
        link = self.link()
        reading = [("list", []), ("detail", [self.student.pk])]
        managing = [
            ("create", []), ("edit", [self.student.pk]), ("status", [self.student.pk]),
            ("guardian_list", []), ("guardian_add", [self.student.pk]),
            ("guardian_detail", [self.guardian.pk]), ("guardian_edit", [self.guardian.pk]),
            ("link_create", [self.student.pk]), ("link_edit", [self.student.pk, link.pk]),
            ("link_activate", [self.student.pk, link.pk]), ("link_deactivate", [self.student.pk, link.pk]),
            ("enroll", [self.student.pk]), ("enrollment_close", [self.student.pk, enrollment.pk]), ("stream_options", []),
        ]
        for role, user in self.users.items():
            self.client.force_login(user)
            manager = role in (User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN)
            reader = manager or role == User.Role.HEADTEACHER
            for name, args in reading + managing:
                allowed = reader if (name, args) in reading else manager
                url = reverse(f"students:{name}", args=args)
                with self.subTest(role=role, view=name):
                    if role == User.Role.TEACHER and (name, args) in reading:
                        self.assertEqual(self.client.get(url).status_code, 200 if name == "list" else 404)
                        self.assertEqual(self.client.post(url, {}).status_code, 405)
                        continue
                    self.assertEqual(self.client.get(url).status_code, 200 if allowed else 403)
                    if not allowed:
                        self.assertEqual(self.client.post(url, {}).status_code, 403)
            self.assertEqual(visible_students(user).exists(), reader)
        self.client.logout()
        for name, args in reading + managing + [("photo", [self.student.pk])]:
            self.assertEqual(self.client.get(reverse(f"students:{name}", args=args)).status_code, 302)

    def test_direct_services_reject_unauthorized_actors(self):
        enrollment, link = self.enroll(), self.link()
        teacher = self.users[User.Role.TEACHER]
        operations = [
            lambda: services.save_student(None, teacher),
            lambda: services.set_student_status(self.student, "inactive", teacher),
            lambda: services.add_guardian_contact(self.student, {}, teacher),
            lambda: services.save_guardian(None, teacher),
            lambda: services.save_link(None, teacher),
            lambda: services.set_link_active(link, False, teacher),
            lambda: services.enroll_student(None, teacher),
            lambda: services.close_enrollment(enrollment, "completed", date(2026, 5, 1), teacher),
        ]
        for operation in operations:
            with self.assertRaises(PermissionDenied):
                operation()

    def test_csrf_and_confirmation_required_for_status_changes(self):
        link = self.link()
        enrollment = self.enroll()
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.actor)
        names = [("create", []), ("edit", [self.student.pk]), ("status", [self.student.pk]), ("guardian_add", [self.student.pk]), ("guardian_edit", [self.guardian.pk]), ("link_create", [self.student.pk]), ("link_deactivate", [self.student.pk, link.pk]), ("enroll", [self.student.pk]), ("enrollment_close", [self.student.pk, enrollment.pk])]
        for name, args in names:
            self.assertEqual(protected.post(reverse(f"students:{name}", args=args), {}).status_code, 403)
        self.client.force_login(self.actor)
        self.client.post(reverse("students:link_deactivate", args=[self.student.pk, link.pk]), {})
        link.refresh_from_db()
        self.assertTrue(link.is_active)
        self.client.get(reverse("students:enrollment_close", args=[self.student.pk, enrollment.pk]))
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, "current")

    def test_nested_resources_are_scoped_to_the_student(self):
        enrollment, link = self.enroll(), self.link()
        second = Student.objects.create(school=self.school, student_id="STD-000002", first_name="Jane", last_name="Doe", date_of_birth=date(2018, 1, 1), admission_date=date(2025, 1, 1))
        self.client.force_login(self.actor)
        for name, pk in (("link_edit", link.pk), ("link_activate", link.pk), ("link_deactivate", link.pk), ("enrollment_close", enrollment.pk)):
            url = reverse(f"students:{name}", args=[second.pk, pk])
            for method in (self.client.get, self.client.post):
                self.assertEqual(method(url).status_code, 404)
        self.assertEqual(self.client.get(reverse("students:detail", args=[99999])).status_code, 404)

    def test_full_registration_link_enrollment_and_status_workflow(self):
        self.client.force_login(self.actor)
        response = self.client.post(reverse("students:create"), self.student_data())
        student = Student.objects.get(student_id="STD-000002")
        self.assertRedirects(response, reverse("students:detail", args=[student.pk]))
        self.assertEqual(student.guardian_links.get().guardian, self.guardian)
        self.assertRedirects(self.client.post(reverse("students:enroll", args=[student.pk]), self.enrollment_data()), reverse("students:detail", args=[student.pk]))
        enrollment = student.enrollments.get()
        self.assertRedirects(self.client.post(reverse("students:enrollment_close", args=[student.pk, enrollment.pk]), {"status": "withdrawn", "completion_date": "2026-05-31", "confirm": "on"}), reverse("students:detail", args=[student.pk]))
        self.assertRedirects(self.client.post(reverse("students:status", args=[student.pk]), {"status": "withdrawn", "confirm": "on"}), reverse("students:detail", args=[student.pk]))
        self.assertEqual(student.enrollments.get().status, "withdrawn")
        self.assertEqual(LogEntry.objects.filter(user=self.actor).count(), 5)

    def test_old_guardian_account_routes_are_removed(self):
        self.client.force_login(self.actor)
        for url in ("/students/guardians/new/", "/students/guardians/existing/"):
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_search_full_name_id_and_historical_filters_apply_to_same_enrollment(self):
        old = self.enroll()
        services.close_enrollment(old, "completed", date(2026, 12, 31), self.actor)
        next_class = AcademicClass.objects.create(section=self.primary, name="P.2")
        self.enroll(academic_year=self.next_year.pk, academic_class=next_class.pk, enrollment_date="2027-01-02")
        self.client.force_login(self.actor)
        for query in ["Mary Wasswa", "STD-000001"]:
            response = self.client.get(reverse("students:list"), {"q": query}, HTTP_HX_REQUEST="true")
            self.assertContains(response, "Mary Wasswa")
            self.assertEqual(response.context["page_obj"].paginator.count, 1)
        response = self.client.get(reverse("students:list"), {"year": self.year.pk, "class": next_class.pk})
        self.assertEqual(response.context["page_obj"].paginator.count, 0)
        response = self.client.get(reverse("students:list"), {"year": self.year.pk, "class": self.academic_class.pk, "section": self.primary.pk})
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        for value in ("bad", "999999999999999999999999999", "-1"):
            response = self.client.get(reverse("students:list"), {"class": value})
            self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_pagination_keeps_filters(self):
        for index in range(22):
            Student.objects.create(school=self.school, student_id=f"TEST-{index}", first_name="Jane", last_name="Doe", date_of_birth=date(2018, 1, 1), admission_date=date(2025, 1, 1))
        self.client.force_login(self.actor)
        response = self.client.get(reverse("students:list"), {"q": "Jane", "status": "active", "page": 2})
        self.assertEqual(len(response.context["page_obj"]), 2)
        self.assertContains(response, "q=Jane&amp;status=active&amp;page=1")

    def test_stream_choices_reject_tampering_and_support_htmx(self):
        self.client.force_login(self.actor)
        response = self.client.get(reverse("students:stream_options"), {"academic_class": self.academic_class.pk}, HTTP_HX_REQUEST="true")
        self.assertContains(response, "East")
        for value in ("bad", "999999999999999999999999999", "-1"):
            response = self.client.get(reverse("students:stream_options"), {"academic_class": value})
            self.assertNotContains(response, "East")
        self.stream.is_active = False
        self.stream.save()
        response = self.client.get(reverse("students:stream_options"), {"academic_class": self.academic_class.pk})
        self.assertNotContains(response, "East")

    def test_profile_escapes_html_and_headteacher_has_no_edit_actions(self):
        Student.objects.filter(pk=self.student.pk).update(first_name="<script>alert(1)</script>")
        self.client.force_login(self.users[User.Role.HEADTEACHER])
        response = self.client.get(reverse("students:detail", args=[self.student.pk]))
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertNotContains(response, reverse("students:edit", args=[self.student.pk]))
        self.assertNotContains(response, reverse("students:enroll", args=[self.student.pk]))
        self.assertIn("no-store", response["Cache-Control"])

    def test_database_conflict_preserves_form_input(self):
        self.client.force_login(self.actor)
        with patch("apps.students.views.services.save_student", side_effect=IntegrityError("conflict")):
            response = self.client.post(reverse("students:create"), self.student_data())
        self.assertContains(response, "Review your entries")
        self.assertContains(response, 'value="Sarah"')
        self.assertEqual(Student.objects.count(), 1)

    def test_missing_school_requires_explicit_setup(self):
        self.client.force_login(self.actor)
        with patch("apps.students.views.School.objects.first", return_value=None):
            self.assertRedirects(self.client.get(reverse("students:create")), reverse("schools:profile"), fetch_redirect_response=False)

    def test_admin_is_read_only_for_all_new_records(self):
        enrollment, link = self.enroll(), self.link()
        self.client.force_login(self.users[User.Role.SUPER_ADMIN])
        for model, record in (("student", self.student), ("guardian", self.guardian), ("studentguardian", link), ("enrollment", enrollment)):
            self.assertEqual(self.client.get(reverse(f"admin:students_{model}_changelist")).status_code, 200)
            detail = reverse(f"admin:students_{model}_change", args=[record.pk])
            self.assertEqual(self.client.get(detail).status_code, 200)
            self.assertEqual(self.client.post(detail, {}).status_code, 403)
            self.assertEqual(self.client.get(reverse(f"admin:students_{model}_add")).status_code, 403)
            self.assertEqual(self.client.post(reverse(f"admin:students_{model}_delete", args=[record.pk]), {"post": "yes"}).status_code, 403)


class StudentPhotoTests(StudentTestCase):
    def setUp(self):
        self.photo_directory = TemporaryDirectory()
        self.addCleanup(self.photo_directory.cleanup)
        self.settings_override = self.settings(PRIVATE_MEDIA_ROOT=Path(self.photo_directory.name))
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def upload(self, name="photo.png", size=(40, 40)):
        output = BytesIO()
        Image.new("RGB", size, color="green").save(output, "PNG")
        return SimpleUploadedFile(name, output.getvalue() + b"<script>trailing-content</script>", content_type="image/png")

    def save_photo(self):
        form = StudentForm(self.student_data(first_name="Mary"), {"photo": self.upload()}, instance=self.student, school=self.school)
        self.assertTrue(form.is_valid(), form.errors)
        return services.save_student(form, self.actor)

    def test_photo_is_reencoded_private_and_served_only_to_readers(self):
        student = self.save_photo()
        self.assertTrue(student.photo.name.endswith(".jpg"))
        self.assertTrue(Path(student.photo.path).is_relative_to(self.photo_directory.name))
        self.assertNotIn(b"trailing-content", Path(student.photo.path).read_bytes())
        with Image.open(student.photo.path) as picture:
            self.assertEqual(picture.format, "JPEG")
        with self.assertRaises(ValueError):
            _ = student.photo.url
        for role, user in self.users.items():
            self.client.force_login(user)
            response = self.client.get(reverse("students:photo", args=[student.pk]))
            if role in (User.Role.SCHOOL_ADMIN, User.Role.SUPER_ADMIN, User.Role.HEADTEACHER):
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "image/jpeg")
                self.assertIn("no-store", response["Cache-Control"])
                self.assertTrue(b"".join(response.streaming_content))
                response.close()
            else:
                self.assertEqual(response.status_code, 404 if role == User.Role.TEACHER else 403)
        self.client.logout()
        self.assertEqual(self.client.get("/media/" + student.photo.name).status_code, 404)
        self.assertEqual(self.client.get("/private_media/" + student.photo.name).status_code, 404)

    def test_invalid_oversized_and_excessive_pixel_uploads_are_rejected(self):
        for upload in [SimpleUploadedFile("bad.png", b"<script>bad</script>"), SimpleUploadedFile("huge.png", b"x" * (5 * 1024 * 1024 + 1)), self.upload(size=(4001, 4000))]:
            form = StudentForm(self.student_data(), {"photo": upload}, school=self.school)
            self.assertFalse(form.is_valid())
            self.assertIn("photo", form.errors)
        self.assertEqual(list(Path(self.photo_directory.name).rglob("*.jpg")), [])

    def test_replacing_and_clearing_photo_removes_previous_file_after_commit(self):
        student = self.save_photo()
        old = Path(student.photo.path)
        form = StudentForm(self.student_data(), {"photo": self.upload()}, instance=student, school=self.school)
        self.assertTrue(form.is_valid(), form.errors)
        with self.captureOnCommitCallbacks(execute=True):
            saved = services.save_student(form, self.actor)
        self.assertFalse(old.exists())
        latest = Path(saved.photo.path)
        form = StudentForm(self.student_data(remove_photo="on"), instance=saved, school=self.school)
        self.assertTrue(form.is_valid(), form.errors)
        with self.captureOnCommitCallbacks(execute=True):
            services.save_student(form, self.actor)
        self.assertFalse(latest.exists())
        saved.refresh_from_db()
        self.assertFalse(saved.photo)

    def test_audit_failure_cleans_new_photo_and_keeps_original(self):
        student = self.save_photo()
        old = Path(student.photo.path)
        form = StudentForm(self.student_data(), {"photo": self.upload()}, instance=student, school=self.school)
        self.assertTrue(form.is_valid(), form.errors)
        with patch("apps.schools.services.LogEntry.objects.create", side_effect=RuntimeError("failed")):
            with self.assertRaises(RuntimeError):
                services.save_student(form, self.actor)
        self.assertTrue(old.exists())
        self.assertEqual(list(Path(self.photo_directory.name).rglob("*.jpg")), [old])

    def test_photo_http_upload_and_edit_page_work_without_public_file_url(self):
        self.client.force_login(self.actor)
        response = self.client.post(reverse("students:edit", args=[self.student.pk]), {**self.student_data(first_name="Mary"), "photo": self.upload()})
        self.assertRedirects(response, reverse("students:detail", args=[self.student.pk]))
        self.assertEqual(self.client.get(reverse("students:edit", args=[self.student.pk])).status_code, 200)
        self.client.force_login(self.users[User.Role.SUPER_ADMIN])
        self.assertEqual(self.client.get(reverse("admin:students_student_change", args=[self.student.pk])).status_code, 200)
