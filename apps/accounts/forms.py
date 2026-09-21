from django import forms
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm, UserCreationForm

from .models import User
from .permissions import assignable_roles


class AccountCreationForm(AdminUserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [choice for choice in User.Role.choices if choice[0] != User.Role.SUPER_ADMIN]

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
