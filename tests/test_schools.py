from datetime import date
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.schools.catalog import CONFIGURATION_TYPES
from apps.schools.forms import AcademicClassForm, CurrentPeriodForm, SchoolForm, SectionForm, StreamForm, TermForm
from apps.schools.models import AcademicClass, AcademicYear, School, Section, Stream, Term
from apps.schools.services import save_configuration, set_current_period, set_record_active
from tests.test_accounts import AccountTestCase


class SchoolTestCase(AccountTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.actor = cls.users[User.Role.SCHOOL_ADMIN]
        cls.school = School.objects.create(name="Example School")
        cls.primary = Section.objects.create(school=cls.school, name="Primary")
        cls.nursery = Section.objects.create(school=cls.school, name="Nursery")
        cls.year = AcademicYear.objects.create(school=cls.school, name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
        cls.next_year = AcademicYear.objects.create(school=cls.school, name="2027", start_date=date(2027, 1, 1), end_date=date(2027, 12, 31))
        cls.term = Term.objects.create(academic_year=cls.year, name="Term 1", start_date=date(2026, 2, 1), end_date=date(2026, 4, 30))
        cls.next_term = Term.objects.create(academic_year=cls.next_year, name="Term 1", start_date=date(2027, 2, 1), end_date=date(2027, 4, 30))
        cls.academic_class = AcademicClass.objects.create(section=cls.primary, name="P.1")
        cls.stream = Stream.objects.create(academic_class=cls.academic_class, name="East")


class ConfigurationDialogTests(SchoolTestCase):
    headers = {"HTTP_HX_REQUEST": "true", "HTTP_HX_TARGET": "configuration-dialog-content"}

    def setUp(self):
        self.client.force_login(self.actor)

    def test_dialog_loads_all_configuration_forms_and_regular_pages_remain(self):
        for kind in CONFIGURATION_TYPES:
            url = reverse("schools:record_create", args=[kind])
            with self.subTest(kind=kind):
                response = self.client.get(url, **self.headers)
                self.assertTemplateUsed(response, "schools/dialog_form.html")
                self.assertNotContains(response, "<!doctype html>")
                self.assertContains(response, 'name="csrfmiddlewaretoken"')
                self.assertTemplateUsed(self.client.get(url), "schools/form.html")

    def test_create_year_link_loads_directly_into_dialog(self):
        response = self.client.get(reverse("schools:record_list", args=["years"]))
        url = reverse("schools:record_create", args=["years"])
        self.assertContains(response, f'href="{url}" hx-get="{url}" hx-target="#configuration-dialog-content"')
        self.assertContains(response, 'id="configuration-dialog"')
        self.assertContains(response, 'app.js?v=login-logo-6')

    def test_invalid_dates_preserve_values_inside_dialog_without_saving(self):
        response = self.client.post(reverse("schools:record_create", args=["years"]), {
            "name": "Invalid year", "start_date": "2030-12-31", "end_date": "2030-01-01",
        }, **self.headers)
        self.assertTemplateUsed(response, "schools/dialog_form.html")
        self.assertTrue(response.context["form"].errors)
        self.assertContains(response, 'value="Invalid year"')
        self.assertFalse(AcademicYear.objects.filter(name="Invalid year").exists())

    def test_create_and_edit_trigger_table_refresh(self):
        response = self.client.post(reverse("schools:record_create", args=["sections"]), {
            "name": "New section", "description": "", "sort_order": 3,
        }, **self.headers)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers["HX-Trigger"], "configurationSaved")
        section = Section.objects.get(name="New section")
        response = self.client.post(reverse("schools:record_edit", args=["sections", section.pk]), {
            "name": "Renamed section", "description": "", "sort_order": 3,
        }, **self.headers)
        self.assertEqual(response.status_code, 204)
        section.refresh_from_db()
        self.assertEqual(section.name, "Renamed section")

    def test_dialog_requests_enforce_roles_and_csrf(self):
        url = reverse("schools:record_create", args=["sections"])
        self.client.force_login(self.users[User.Role.TEACHER])
        self.assertEqual(self.client.get(url, **self.headers).status_code, 403)
        self.assertEqual(self.client.post(url, {"name": "Forbidden"}, **self.headers).status_code, 403)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        self.assertEqual(client.post(url, {"name": "No token"}, **self.headers).status_code, 403)


class ConfigurationModelTests(SchoolTestCase):
    def test_database_allows_only_one_school(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            School.objects.create(id=2, name="Another school")

    def test_names_are_case_insensitively_unique_within_parent(self):
        duplicates = [
            (Section, {"school": self.school, "name": "PRIMARY"}),
            (AcademicYear, {"school": self.school, "name": "2026", "start_date": date(2028, 1, 1), "end_date": date(2028, 12, 31)}),
            (AcademicClass, {"section": self.primary, "name": "p.1"}),
            (Stream, {"academic_class": self.academic_class, "name": "east"}),
            (Term, {"academic_year": self.year, "name": "TERM 1", "start_date": date(2026, 6, 1), "end_date": date(2026, 8, 1)}),
        ]
        for model, fields in duplicates:
            with self.subTest(model=model), self.assertRaises(IntegrityError), transaction.atomic():
                model.objects.create(**fields)
        other_class = AcademicClass.objects.create(section=self.nursery, name="P.1")
        Stream.objects.create(academic_class=other_class, name="East")

    def test_year_and_term_dates_have_database_constraints(self):
        invalid = [
            (AcademicYear, {"school": self.school, "name": "Bad dates", "start_date": date(2030, 12, 1), "end_date": date(2030, 1, 1)}),
            (Term, {"academic_year": self.year, "name": "Bad dates", "start_date": date(2026, 8, 1), "end_date": date(2026, 6, 1)}),
        ]
        for model, fields in invalid:
            with self.subTest(fields=fields), self.assertRaises(IntegrityError), transaction.atomic():
                model.objects.create(**fields)

    def test_year_overlap_including_shared_endpoints_is_rejected(self):
        year = AcademicYear(school=self.school, name="Overlapping", start_date=date(2026, 12, 31), end_date=date(2027, 12, 31))
        with self.assertRaisesMessage(ValidationError, "cannot overlap"):
            year.full_clean()

    def test_term_dates_are_contained_and_do_not_overlap(self):
        cases = [
            (date(2025, 12, 31), date(2026, 1, 15), "within their academic year"),
            (date(2026, 12, 1), date(2027, 1, 1), "within their academic year"),
            (date(2026, 4, 30), date(2026, 7, 1), "cannot overlap"),
        ]
        for start, end, message in cases:
            with self.subTest(start=start):
                term = Term(academic_year=self.year, name="Term 2", start_date=start, end_date=end)
                with self.assertRaisesMessage(ValidationError, message):
                    term.full_clean()

    def test_year_cannot_shrink_past_existing_terms_even_inactive_ones(self):
        self.term.is_active = False
        self.term.save()
        self.year.start_date = date(2026, 3, 1)
        with self.assertRaisesMessage(ValidationError, "contain all of its existing terms"):
            self.year.full_clean()

    def test_parent_relationships_cannot_be_reassigned(self):
        another_class = AcademicClass.objects.create(section=self.nursery, name="Top")
        for record, field, value in [
            (self.academic_class, "section", self.nursery),
            (self.stream, "academic_class", another_class),
            (self.term, "academic_year", self.next_year),
        ]:
            with self.subTest(record=record):
                setattr(record, field, value)
                with self.assertRaisesMessage(ValidationError, "parent cannot be changed"):
                    record.full_clean()

    def test_class_can_exist_without_streams(self):
        academic_class = AcademicClass(section=self.nursery, name="Top")
        academic_class.full_clean()
        academic_class.save()
        self.assertEqual(academic_class.streams.count(), 0)

    def test_referenced_parents_are_protected_from_deletion(self):
        for record in [self.school, self.primary, self.year, self.academic_class]:
            with self.subTest(record=record), self.assertRaises(ProtectedError):
                record.delete()


class ConfigurationServiceTests(SchoolTestCase):
    def test_current_period_changes_atomically_and_retains_history(self):
        set_current_period(self.actor, self.year, self.term)
        self.school.refresh_from_db()
        self.assertEqual((self.school.current_academic_year_id, self.school.current_term_id), (self.year.pk, self.term.pk))
        set_current_period(self.actor, self.next_year, self.next_term)
        self.school.refresh_from_db()
        self.assertEqual((self.school.current_academic_year_id, self.school.current_term_id), (self.next_year.pk, self.next_term.pk))
        self.assertTrue(Term.objects.filter(pk=self.term.pk, is_active=True).exists())
        self.assertTrue(AcademicYear.objects.filter(pk=self.year.pk, is_active=True).exists())
        self.assertEqual(self.school.updated_by, self.actor)
        self.assertEqual(LogEntry.objects.filter(change_message="Changed current academic period.").count(), 2)

    def test_current_term_must_belong_to_current_year(self):
        set_current_period(self.actor, self.year, self.term)
        with self.assertRaisesMessage(ValidationError, "belong to the current academic year"):
            set_current_period(self.actor, self.next_year, self.term)
        self.school.refresh_from_db()
        self.assertEqual(self.school.current_academic_year_id, self.year.pk)
        self.assertEqual(self.school.current_term_id, self.term.pk)

    def test_current_period_can_have_no_term_or_be_cleared(self):
        set_current_period(self.actor, self.year, None)
        self.school.refresh_from_db()
        self.assertIsNone(self.school.current_term_id)
        set_current_period(self.actor, None, None)
        self.school.refresh_from_db()
        self.assertIsNone(self.school.current_academic_year_id)

    def test_inactive_periods_and_term_without_year_are_rejected(self):
        self.next_term.is_active = False
        self.next_term.save()
        with self.assertRaises(ValidationError):
            set_current_period(self.actor, self.next_year, self.next_term)
        self.next_year.is_active = False
        self.next_year.save()
        with self.assertRaises(ValidationError):
            set_current_period(self.actor, self.next_year, None)
        with self.assertRaises(ValidationError):
            set_current_period(self.actor, None, self.term)
        with self.assertRaises(IntegrityError), transaction.atomic():
            School.objects.filter(pk=1).update(current_term=self.term)

    def test_current_year_and_term_cannot_be_deactivated(self):
        set_current_period(self.actor, self.year, self.term)
        for record in [self.year, self.term]:
            with self.subTest(record=record), self.assertRaisesMessage(ValidationError, "current"):
                set_record_active(record, False, self.actor)
            record.refresh_from_db()
            self.assertTrue(record.is_active)

    def test_deactivation_requires_children_first_and_preserves_records(self):
        for record in [self.primary, self.academic_class, self.year]:
            with self.subTest(record=record), self.assertRaisesMessage(ValidationError, "first"):
                set_record_active(record, False, self.actor)
        for record in [self.stream, self.academic_class, self.primary, self.term, self.year]:
            set_record_active(record, False, self.actor)
            record.refresh_from_db()
            self.assertFalse(record.is_active)
        for record in [self.stream, self.academic_class, self.term]:
            with self.subTest(record=record), self.assertRaises(ValidationError):
                set_record_active(record, True, self.actor)
        for record in [self.primary, self.academic_class, self.stream, self.year, self.term]:
            set_record_active(record, True, self.actor)
            record.refresh_from_db()
            self.assertTrue(record.is_active)

    def test_audit_failure_rolls_back_configuration_write(self):
        form = SectionForm({"name": "Secondary", "description": "", "sort_order": 3}, school=self.school)
        self.assertTrue(form.is_valid(), form.errors)
        with patch("apps.schools.services.LogEntry.objects.create", side_effect=RuntimeError("Audit unavailable")):
            with self.assertRaises(RuntimeError):
                save_configuration(form, self.actor)
        self.assertFalse(Section.objects.filter(name="Secondary").exists())

    def test_stale_profile_edit_does_not_overwrite_current_period(self):
        form = SchoolForm({"name": "Renamed School", "currency_code": "UGX"}, instance=self.school)
        self.assertTrue(form.is_valid(), form.errors)
        set_current_period(self.actor, self.year, self.term)
        save_configuration(form, self.actor)
        self.school.refresh_from_db()
        self.assertEqual(self.school.name, "Renamed School")
        self.assertEqual(self.school.current_term_id, self.term.pk)

    def test_parent_is_rechecked_after_form_validation(self):
        form = AcademicClassForm({"section": self.nursery.pk, "name": "Top", "sort_order": 0}, school=self.school)
        self.assertTrue(form.is_valid(), form.errors)
        set_record_active(self.nursery, False, self.actor)
        with self.assertRaisesMessage(ValidationError, "active section"):
            save_configuration(form, self.actor)
        self.assertFalse(AcademicClass.objects.filter(name="Top").exists())

    def test_services_require_authorized_actor(self):
        guardian = self.users[User.Role.STUDENT]
        form = SectionForm({"name": "Unauthorized", "sort_order": 0}, school=self.school)
        self.assertTrue(form.is_valid())
        for operation in [
            lambda: save_configuration(form, guardian),
            lambda: set_current_period(guardian, self.year, self.term),
            lambda: set_record_active(self.stream, False, guardian),
        ]:
            with self.assertRaises(PermissionDenied):
                operation()


class ConfigurationViewTests(SchoolTestCase):
    def setUp(self):
        self.client.force_login(self.actor)

    def test_every_configuration_endpoint_checks_every_role(self):
        urls = [reverse(f"schools:{name}") for name in ("overview", "profile", "current_period", "term_options")]
        fixtures = {"sections": self.primary, "years": self.year, "terms": self.term, "classes": self.academic_class, "streams": self.stream}
        for kind, record in fixtures.items():
            urls += [reverse("schools:record_list", args=[kind]), reverse("schools:record_create", args=[kind])]
            urls += [reverse(f"schools:{action}", args=[kind, record.pk]) for action in ("record_edit", "record_activate", "record_deactivate")]
        for role, user in self.users.items():
            self.client.force_login(user)
            allowed = role in (User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN)
            for url in urls:
                with self.subTest(role=role, url=url):
                    self.assertEqual(self.client.get(url).status_code, 200 if allowed else 403)
                    if not allowed:
                        self.assertEqual(self.client.post(url, {}).status_code, 403)
            if role == User.Role.STUDENT:
                continue
            home = self.client.get(reverse(f"dashboard:{role}"), follow=True)
            if allowed:
                self.assertContains(home, "School setup")
            else:
                self.assertNotContains(home, "School setup")
        self.client.logout()
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)

    def test_create_all_record_types_without_changing_code(self):
        records = [
            ("sections", {"name": "Reception", "description": "Early years", "sort_order": 1}),
            ("years", {"name": "2028/29", "start_date": "2028-08-01", "end_date": "2029-06-30"}),
            ("terms", {"academic_year": self.year.pk, "name": "Summer", "start_date": "2026-06-01", "end_date": "2026-08-31"}),
            ("classes", {"section": self.nursery.pk, "name": "Top", "sort_order": 2}),
            ("streams", {"academic_class": self.academic_class.pk, "name": "West"}),
        ]
        for kind, data in records:
            with self.subTest(kind=kind):
                response = self.client.post(reverse("schools:record_create", args=[kind]), {**data, "is_active": "", "created_by": self.users[User.Role.SUPER_ADMIN].pk, "school": 99})
                self.assertRedirects(response, reverse("schools:record_list", args=[kind]))
                obj = CONFIGURATION_TYPES[kind].model.objects.get(name=data["name"])
                self.assertTrue(obj.is_active)
                self.assertEqual(obj.created_by, self.actor)
                self.assertEqual(obj.updated_by, self.actor)
                self.assertTrue(LogEntry.objects.filter(content_type__model=obj._meta.model_name, object_id=str(obj.pk), user=self.actor).exists())

    def test_terms_follow_dates_on_creation_edit_and_period_choices(self):
        create_url = reverse("schools:record_create", args=["terms"])
        self.assertNotContains(self.client.get(create_url), 'name="sequence"')
        for name, start, end in [
            ("A later term", "2026-09-01", "2026-12-01"),
            ("Z earlier term", "2026-06-01", "2026-08-01"),
        ]:
            response = self.client.post(create_url, {
                "academic_year": self.year.pk, "name": name,
                "start_date": start, "end_date": end,
            })
            self.assertRedirects(response, reverse("schools:record_list", args=["terms"]))
        later = Term.objects.get(name="A later term")
        earlier = Term.objects.get(name="Z earlier term")
        response = self.client.get(reverse("schools:record_list", args=["terms"]))
        self.assertEqual([row["record"].pk for row in response.context["rows"]], [self.next_term.pk, self.term.pk, earlier.pk, later.pk])
        choices = CurrentPeriodForm({"academic_year": self.year.pk}, school=self.school).fields["term"].queryset
        self.assertEqual(list(choices), [self.term, earlier, later])
        set_current_period(self.actor, self.year, later)
        edit_url = reverse("schools:record_edit", args=["terms", later.pk])
        self.assertNotContains(self.client.get(edit_url), 'name="sequence"')
        response = self.client.post(edit_url, {
            "academic_year": self.year.pk, "name": later.name,
            "start_date": "2026-01-01", "end_date": "2026-01-31",
        })
        self.assertRedirects(response, reverse("schools:record_list", args=["terms"]))
        response = self.client.get(reverse("schools:term_options"), {"academic_year": self.year.pk}, headers={"HX-Request": "true"})
        self.assertEqual(list(response.context["terms"]), [later, self.term, earlier])
        self.school.refresh_from_db()
        self.assertEqual(self.school.current_term_id, later.pk)

    def test_profile_changes_update_identity_and_policy_values(self):
        response = self.client.post(reverse("schools:profile"), {
            "name": "Our <School>", "motto": "Learning together", "currency_code": "kes",
            "enable_ranking": "on", "require_fee_clearance_for_reports": "on",
        })
        self.assertRedirects(response, reverse("schools:overview"))
        self.school.refresh_from_db()
        self.assertEqual(self.school.currency_code, "KES")
        self.assertTrue(self.school.enable_ranking)
        self.assertTrue(self.school.require_fee_clearance_for_reports)
        response = self.client.get(reverse("accounts:profile"))
        self.assertContains(response, "Our &lt;School&gt;")
        self.assertNotContains(response, "Our <School>")

    def test_edit_cannot_move_parents_or_change_status_via_hidden_fields(self):
        response = self.client.post(reverse("schools:record_edit", args=["classes", self.academic_class.pk]), {
            "name": "Primary One", "section": self.nursery.pk, "sort_order": 1, "is_active": "",
        })
        self.assertRedirects(response, reverse("schools:record_list", args=["classes"]))
        self.academic_class.refresh_from_db()
        self.assertEqual(self.academic_class.section_id, self.primary.pk)
        self.assertEqual(self.academic_class.name, "Primary One")
        self.assertTrue(self.academic_class.is_active)

    def test_inactive_parents_are_not_selectable_on_create(self):
        set_record_active(self.nursery, False, self.actor)
        form = AcademicClassForm({"section": self.nursery.pk, "name": "Top", "sort_order": 1}, school=self.school)
        self.assertFalse(form.is_valid())
        self.assertIn("section", form.errors)
        set_record_active(self.stream, False, self.actor)
        set_record_active(self.academic_class, False, self.actor)
        form = StreamForm({"academic_class": self.academic_class.pk, "name": "West"}, school=self.school)
        self.assertFalse(form.is_valid())
        self.assertIn("academic_class", form.errors)
        form = TermForm({"academic_year": 999999, "name": "Invalid", "start_date": "2026-09-01", "end_date": "2026-12-01"}, school=self.school)
        self.assertFalse(form.is_valid())

    def test_duplicate_and_invalid_forms_keep_submitted_data(self):
        response = self.client.post(reverse("schools:record_create", args=["sections"]), {"name": " primary ", "description": "Keep this input", "sort_order": 1})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertContains(response, "Keep this input")
        self.assertContains(response, "A section with this name already exists.")
        self.assertNotContains(response, "schools_section_name_unique")
        self.assertEqual(Section.objects.filter(name__iexact="Primary").count(), 1)

    def test_current_period_form_and_htmx_choices_reject_mismatched_terms(self):
        response = self.client.post(reverse("schools:current_period"), {"academic_year": self.year.pk, "term": self.next_term.pk})
        self.assertEqual(response.status_code, 200)
        self.assertIn("term", response.context["form"].errors)
        self.school.refresh_from_db()
        self.assertIsNone(self.school.current_term_id)
        response = self.client.get(reverse("schools:term_options"), {"academic_year": self.year.pk}, headers={"HX-Request": "true"})
        self.assertContains(response, f'value="{self.term.pk}"')
        self.assertNotContains(response, f'value="{self.next_term.pk}"')
        self.assertContains(self.client.get(reverse("schools:term_options"), {"academic_year": "bad"}), "No current term")
        response = self.client.post(reverse("schools:current_period"), {"academic_year": self.year.pk, "term": self.term.pk})
        self.assertRedirects(response, reverse("schools:overview"))

    def test_status_actions_require_confirmation_and_show_dependency_errors(self):
        url = reverse("schools:record_deactivate", args=["sections", self.primary.pk])
        self.client.get(url)
        self.client.post(url, {})
        self.primary.refresh_from_db()
        self.assertTrue(self.primary.is_active)
        response = self.client.post(url, {"confirm": "on"})
        self.assertContains(response, "active classes first")
        stream_url = reverse("schools:record_deactivate", args=["streams", self.stream.pk])
        self.assertRedirects(self.client.post(stream_url, {"confirm": "on"}), reverse("schools:record_list", args=["streams"]))
        self.stream.refresh_from_db()
        self.assertFalse(self.stream.is_active)

    def test_search_pagination_and_status_filter(self):
        Section.objects.bulk_create([Section(school=self.school, name=f"Custom {i:02}") for i in range(23)])
        response = self.client.get(reverse("schools:record_list", args=["sections"]), {"q": "Custom", "status": "active"}, headers={"HX-Request": "true"})
        self.assertEqual(response.context["page_obj"].paginator.count, 23)
        self.assertEqual(len(response.context["page_obj"]), 20)
        self.assertContains(response, "q=Custom&amp;status=active&amp;page=2")
        self.assertContains(response, 'id="configuration-results"')
        response = self.client.get(reverse("schools:record_list", args=["sections"]), {"status": "inactive"})
        self.assertContains(response, "No records match your search")

    def test_csrf_and_invalid_resource_ids(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        for url in [reverse("schools:profile"), reverse("schools:current_period"), reverse("schools:record_create", args=["sections"]), reverse("schools:record_edit", args=["sections", self.primary.pk]), reverse("schools:record_deactivate", args=["sections", self.primary.pk])]:
            self.assertEqual(client.post(url, {}).status_code, 403)
        self.assertEqual(self.client.get(reverse("schools:record_list", args=["unknown"])).status_code, 404)
        self.assertEqual(self.client.post(reverse("schools:record_edit", args=["sections", 999999]), {}).status_code, 404)

    def test_superuser_admin_configuration_validates_and_protects_school(self):
        self.client.force_login(self.users[User.Role.SUPER_ADMIN])
        url = reverse("admin:schools_school_change", args=[self.school.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, {"name": "Missing required fields"}).status_code, 200)
        self.school.refresh_from_db()
        self.assertNotEqual(self.school.name, "Missing required fields")
        self.assertEqual(self.client.get(reverse("admin:schools_school_add")).status_code, 403)
        self.assertEqual(self.client.post(reverse("admin:schools_school_delete", args=[self.school.pk]), {"post": "yes"}).status_code, 200)


class InitialSchoolSetupTests(AccountTestCase):
    def test_first_setup_is_explicit_and_does_not_seed_fixed_school_structure(self):
        actor = self.users[User.Role.SCHOOL_ADMIN]
        self.client.force_login(actor)
        self.assertContains(self.client.get(reverse("schools:overview")), "Create your school profile first")
        self.assertEqual(School.objects.count(), 0)
        self.assertRedirects(self.client.get(reverse("schools:record_create", args=["sections"])), reverse("schools:profile"))
        self.assertRedirects(self.client.post(reverse("schools:profile"), {"name": "A New School", "currency_code": "UGX"}), reverse("schools:overview"))
        school = School.objects.get()
        self.assertEqual(school.created_by, actor)
        self.assertEqual(school.sections.count(), 0)
        self.assertEqual(school.academic_years.count(), 0)
