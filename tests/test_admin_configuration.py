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

    def test_sensitive_records_and_non_superusers_remain_protected(self):
        request = RequestFactory().get('/admin/')
        request.user = self.users[User.Role.SUPER_ADMIN]
        self.assertFalse(admin.site._registry[Mark].has_change_permission(request))
        self.assertFalse(admin.site._registry[Section].has_delete_permission(request, self.primary))
        request.user = self.users[User.Role.SCHOOL_ADMIN]
        self.assertFalse(admin.site._registry[Section].has_add_permission(request))
