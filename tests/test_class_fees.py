from datetime import date
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.accounts.models import User
from apps.finance.models import FeeCharge
from apps.finance.services import assign_charge, assign_class_charges
from apps.students.models import Enrollment, Student
from tests.test_finance import FinanceTestCase


class ClassFeeTests(FinanceTestCase):
    def extra_enrollment(self, number, **changes):
        student = Student.objects.create(school=self.school, student_id=f'STD-{number:06d}', first_name='Test', last_name='Student', gender='female', date_of_birth=date(2018, 1, 1), admission_date=date(2025, 1, 1))
        return Enrollment.objects.create(student=student, academic_year=self.year, section=self.academic_class.section, academic_class=self.academic_class, enrollment_date=date(2026, 1, 2), **changes)

    def test_assigns_class_and_skips_existing_even_cancelled(self):
        from apps.finance.services import cancel_charge
        other = self.extra_enrollment(2)
        cancel_charge(self.charge, 'Incorrect fee', self.actor)
        self.assertEqual(assign_class_charges(self.structure, self.actor), (1, 1))
        self.assertTrue(FeeCharge.objects.filter(enrollment=other, created_by=self.actor).exists())
        self.assertEqual(assign_class_charges(self.structure, self.actor), (0, 2))

    def test_stream_and_current_enrollment_scope(self):
        from apps.schools.models import Stream
        stream = Stream.objects.create(academic_class=self.academic_class, name='Bulk fees stream')
        included = self.extra_enrollment(2, stream=stream)
        self.extra_enrollment(3, stream=stream, status=Enrollment.Status.COMPLETED, completion_date=date(2026, 2, 1))
        self.structure.stream = stream
        self.structure.save()
        self.assertEqual(assign_class_charges(self.structure, self.actor), (1, 0))
        self.assertTrue(FeeCharge.objects.filter(enrollment=included).exists())

    def test_atomic_rollback(self):
        self.extra_enrollment(2)
        self.extra_enrollment(3)
        calls = 0

        def fail_second(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValidationError('Failed audit')
            return assign_charge(*args)

        with patch('apps.finance.services.assign_charge', side_effect=fail_second):
            with self.assertRaises(ValidationError):
                assign_class_charges(self.structure, self.actor)
        self.assertEqual(FeeCharge.objects.count(), 1)

    def test_permissions_confirmation_and_form_workflow(self):
        url = reverse('finance:class_charge_create')
        self.extra_enrollment(2)
        for role in (User.Role.TEACHER, User.Role.HEADTEACHER, User.Role.GUARDIAN):
            self.client.force_login(self.users[role])
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {'structure': self.structure.pk, 'confirm': 'on'}).status_code, 403)
            with self.assertRaises(PermissionDenied):
                assign_class_charges(self.structure, self.users[role])
        self.client.force_login(self.users[User.Role.BURSAR])
        self.assertContains(self.client.get(url), 'All streams')
        self.assertEqual(self.client.post(url, {'structure': self.structure.pk}).status_code, 200)
        self.assertEqual(FeeCharge.objects.count(), 1)
        response = self.client.post(url, {'structure': self.structure.pk, 'confirm': 'on'}, follow=True)
        self.assertContains(response, 'Fees assigned to 1 students. 1 existing assignments skipped.')

    def test_inactive_and_empty_structure(self):
        self.structure.is_active = False
        self.structure.save()
        with self.assertRaises(ValidationError):
            assign_class_charges(self.structure, self.actor)
        self.structure.is_active = True
        self.structure.save()
        Enrollment.objects.update(status=Enrollment.Status.COMPLETED, completion_date=date(2026, 2, 1))
        with self.assertRaisesMessage(ValidationError, 'No matching'):
            assign_class_charges(self.structure, self.actor)
