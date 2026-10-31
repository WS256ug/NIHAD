from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import AccountChangeForm, AccountCreationForm
from .models import User


@admin.register(User)
class AccountAdmin(UserAdmin):
    form = AccountChangeForm
    add_form = AccountCreationForm
    list_display = ("username", "email", "first_name", "last_name", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    readonly_fields = ("date_joined", "last_login", "updated_at")
    fieldsets = UserAdmin.fieldsets + (("School role", {"fields": ("role", "updated_at")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Profile", {"fields": ("email", "first_name", "last_name", "role")}),
    )
