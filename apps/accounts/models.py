from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from .managers import UserManager


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = "super_admin", "Super Admin"
        SCHOOL_ADMIN = "school_admin", "School Admin"
        HEADTEACHER = "headteacher", "Headteacher"
        TEACHER = "teacher", "Teacher"
        BURSAR = "bursar", "Bursar / Finance"
        STUDENT = "student", "Student portal"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    must_change_password = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    def clean(self):
        super().clean()
        if self.is_superuser != (self.role == self.Role.SUPER_ADMIN):
            raise ValidationError("The Super Admin role and superuser status must be assigned together.")
        if self.is_superuser and not self.is_staff:
            raise ValidationError("Super Admin accounts must have staff status.")
        if self.pk and hasattr(self, "portal_student"):
            if self.role != self.Role.STUDENT or self.username != self.portal_student.student_id:
                raise ValidationError("Student portal identity must match the student's permanent registration number.")
        if self.pk and self.role != self.Role.TEACHER and hasattr(self, "teacher_profile"):
            raise ValidationError("An account with a teacher profile must retain the Teacher role.")

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(is_superuser=True, is_staff=True, role="super_admin")
                    | (models.Q(is_superuser=False) & ~models.Q(role="super_admin"))
                ),
                name="accounts_superuser_role_consistent",
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=[
                    "super_admin", "school_admin", "headteacher", "teacher", "bursar", "student",
                ]),
                name="accounts_user_valid_role",
            ),
            models.CheckConstraint(condition=~models.Q(role="student") | models.Q(is_staff=False, is_superuser=False), name="accounts_student_not_staff"),
        ]
