from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from django.views.decorators.cache import never_cache

from . import views

app_name = "accounts"
urlpatterns = [
    path("login/", views.SignInView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path("users/", views.user_list, name="user_list"),
    path("users/new/", views.user_create, name="user_create"),
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("users/<int:pk>/activate/", views.user_status, {"activate": True}, name="user_activate"),
    path("users/<int:pk>/deactivate/", views.user_status, {"activate": False}, name="user_deactivate"),
    path("password/change/", views.AccountPasswordChangeView.as_view(
        template_name="registration/password_change_form.html",
        success_url=reverse_lazy("accounts:password_change_done"),
    ), name="password_change"),
    path("password/change/done/", never_cache(auth_views.PasswordChangeDoneView.as_view(
        template_name="registration/password_change_done.html",
    )), name="password_change_done"),
    path("password/reset/", never_cache(auth_views.PasswordResetView.as_view(
        template_name="registration/password_reset_form.html",
        email_template_name="registration/password_reset_email.txt",
        subject_template_name="registration/password_reset_subject.txt",
        success_url=reverse_lazy("accounts:password_reset_done"),
    )), name="password_reset"),
    path("password/reset/sent/", never_cache(auth_views.PasswordResetDoneView.as_view(
        template_name="registration/password_reset_done.html",
    )), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="registration/password_reset_confirm.html",
        success_url=reverse_lazy("accounts:password_reset_complete"),
    ), name="password_reset_confirm"),
    path("password/reset/complete/", never_cache(auth_views.PasswordResetCompleteView.as_view(
        template_name="registration/password_reset_complete.html",
    )), name="password_reset_complete"),
]
