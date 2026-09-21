from django.contrib.auth.models import UserManager as DjangoUserManager


class UserManager(DjangoUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", self.model.Role.SUPER_ADMIN)
        if extra_fields["role"] != self.model.Role.SUPER_ADMIN:
            raise ValueError("Superusers must have the Super Admin role.")
        return super().create_superuser(username, email, password, **extra_fields)
