from django.urls import path

from apps.accounts.models import User

from . import views

app_name = "dashboard"
urlpatterns = [path("", views.home, name="home")]
urlpatterns += [
    path(f"workspace/{role.replace('_', '-')}/", views.workspace, {"role": role}, name=role)
    for role in User.Role.values
]
