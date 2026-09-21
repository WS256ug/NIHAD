from django.contrib.auth.models import AbstractUser
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

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=[
                    "super_admin", "school_admin", "headteacher", "teacher", "bursar", "guardian",
                ]),
                name="accounts_user_valid_role",
            ),
        ]
