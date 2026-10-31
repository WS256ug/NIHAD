from django.contrib.admin import AdminSite
from django.contrib.admin.forms import AdminAuthenticationForm


class SchoolAdminAuthenticationForm(AdminAuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_superuser:
            raise self.get_invalid_login_error()


class SchoolAdminSite(AdminSite):
    login_form = SchoolAdminAuthenticationForm

    def has_permission(self, request):
        # School Admins use the scoped account portal, not Django's permission editor.
        return request.user.is_active and request.user.is_staff and request.user.is_superuser
