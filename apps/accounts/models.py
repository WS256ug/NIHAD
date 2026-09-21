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
        GUARDIAN = "guardian", "Guardian"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.GUARDIAN)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    def clean(self):
        super().clean()
        if self.is_superuser != (self.role == self.Role.SUPER_ADMIN):
            raise ValidationError("The Super Admin role and superuser status must be assigned together.")
        if self.is_superuser and not self.is_staff:
            raise ValidationError("Super Admin accounts must have staff status.")

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
                    "super_admin", "school_admin", "headteacher", "teacher", "bursar", "guardian",
                ]),
                name="accounts_user_valid_role",
            ),
        ]
