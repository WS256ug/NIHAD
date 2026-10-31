from django.contrib import admin
from django.test import RequestFactory
from django.urls import reverse
from apps.accounts.models import User
from apps.schools.models import Section
from apps.academics.models import Mark
from tests.test_schools import SchoolTestCase


class SuperuserConfigurationTests(SchoolTestCase):
    def test_superuser_creates_edits_and_deletes_unused_section(self):
        user = self.users[User.Role.SUPER_ADMIN]
        self.client.force_login(user)
        data = {'school': self.school.pk, 'name': 'Extra section', 'sort_order': 9, 'is_active': 'on'}
        self.assertEqual(self.client.post(reverse('admin:schools_section_add'), data).status_code, 302)
        section = Section.objects.get(name='Extra section')
        self.assertEqual(section.created_by, user)
        data['name'] = 'Updated section'
        self.assertEqual(self.client.post(reverse('admin:schools_section_change', args=[section.pk]), data).status_code, 302)
        section.refresh_from_db()
        self.assertEqual(section.name, 'Updated section')
        self.assertEqual(section.updated_by, user)
        self.assertEqual(self.client.post(reverse('admin:schools_section_delete', args=[section.pk]), {'post': 'yes'}).status_code, 302)
        self.assertFalse(Section.objects.filter(pk=section.pk).exists())

    def test_all_registered_records_allow_superuser_crud_only(self):
        request = RequestFactory().get('/admin/')
        request.user = self.users[User.Role.SUPER_ADMIN]
        for model, model_admin in admin.site._registry.items():
            if model._meta.app_label not in {"schools", "students", "academics", "finance", "expenses", "reports", "promotions"}:
                continue
            with self.subTest(model=model._meta.label):
                self.assertTrue(model_admin.has_view_permission(request))
                self.assertTrue(model_admin.has_change_permission(request))
                self.assertTrue(model_admin.has_delete_permission(request))
                if model._meta.model_name != "school":
                    self.assertTrue(model_admin.has_add_permission(request))
        for user in (self.users[User.Role.SCHOOL_ADMIN], self.users[User.Role.TEACHER]):
            request.user = user
            for model_admin in admin.site._registry.values():
                if isinstance(model_admin, type(admin.site._registry[Section])):
                    self.assertFalse(model_admin.has_add_permission(request))
                    self.assertFalse(model_admin.has_change_permission(request))
                    self.assertFalse(model_admin.has_delete_permission(request))
        request.user = self.users[User.Role.SUPER_ADMIN]
        request.user.is_active = False
        self.assertFalse(admin.site._registry[Mark].has_change_permission(request))

    def test_superuser_creates_corrects_and_deletes_financial_record(self):
        from apps.expenses.models import OtherIncome
        from django.utils import timezone
        from django.core.exceptions import ValidationError
        self.client.force_login(self.users[User.Role.SUPER_ADMIN])
        data = {"school": self.school.pk, "description": "Donation", "amount": "100.00",
                "date": timezone.localdate().isoformat(), "method": "cash", "source": "Donor"}
        self.assertEqual(self.client.post(reverse("admin:expenses_otherincome_add"), data).status_code, 302)
        record = OtherIncome.objects.get(description="Donation")
        self.assertEqual(record.currency, self.school.currency_code)
        record.description = "Outside admin"
        with self.assertRaises(ValidationError):
            record.full_clean()
        data["description"] = "Corrected donation"
        self.assertEqual(self.client.post(reverse("admin:expenses_otherincome_change", args=[record.pk]), data).status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.description, "Corrected donation")
        self.assertEqual(record.updated_by, self.users[User.Role.SUPER_ADMIN])
        self.assertEqual(self.client.post(reverse("admin:expenses_otherincome_delete", args=[record.pk]), {"post": "yes"}).status_code, 302)
        self.assertFalse(OtherIncome.objects.filter(pk=record.pk).exists())

    def test_superuser_student_creation_allocates_unique_numbers(self):
        from apps.students.models import Student
        self.client.force_login(self.users[User.Role.SUPER_ADMIN])
        data = {"school": self.school.pk, "first_name": "Admin", "last_name": "Student",
                "gender": "female", "date_of_birth": "2020-01-01", "admission_date": "2026-01-01", "status": "active"}
        for _ in range(2):
            response = self.client.post(reverse("admin:students_student_add"), data)
            self.assertEqual(response.status_code, 302)
        identifiers = list(Student.objects.values_list("student_id", flat=True))
        self.assertEqual(len(set(identifiers)), 2)
        self.assertEqual(set(identifiers), {"NBS-0001", "NBS-0002"})
