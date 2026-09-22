from django import forms
from django.contrib.auth.forms import AdminUserCreationForm, AuthenticationForm, UserChangeForm, UserCreationForm

from .models import User
from .permissions import assignable_roles


class AccountCreationForm(AdminUserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [choice for choice in User.Role.choices if choice[0] not in (User.Role.SUPER_ADMIN, User.Role.STUDENT)]

    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name", "role")


class AccountChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"


class ScopedAccountFormMixin:
    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        roles = assignable_roles(actor)
        self.fields["role"].choices = [choice for choice in User.Role.choices if choice[0] in roles]
        self.fields["email"].required = True


class ManagedAccountCreationForm(ScopedAccountFormMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "role")


class ManagedAccountChangeForm(ScopedAccountFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "role")


class AccountStatusForm(forms.Form):
    confirm = forms.BooleanField(label="I confirm this account status change.")


class StaffSignInForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.role == User.Role.STUDENT:
            raise forms.ValidationError("Use the Student portal sign-in page with the student's registration number.", code="invalid_login")


class StudentSignInForm(AuthenticationForm):
    username = forms.CharField(label="Student registration number", max_length=30)

    def clean_username(self):
        return self.cleaned_data["username"].strip().upper()

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.role != User.Role.STUDENT or not hasattr(user, "portal_student"):
            raise forms.ValidationError("Enter a valid registration number and password.", code="invalid_login")
