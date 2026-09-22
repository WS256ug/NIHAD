from django.urls import path
from . import portal, views

app_name = "students"

urlpatterns = [
    path("portal/login/", portal.PortalSignInView.as_view(), name="portal_login"),
    path("portal/", portal.home, name="portal_home"),
    path("portal/photo/", portal.photo, name="portal_photo"),
    path("", views.student_list, name="list"),
    path("new/", views.student_form, name="create"),
    path("stream-options/", views.stream_options, name="stream_options"),
    path("guardians/", views.guardian_list, name="guardian_list"),
    path("guardians/<int:pk>/", views.guardian_detail, name="guardian_detail"),
    path("guardians/<int:pk>/edit/", views.guardian_form, name="guardian_edit"),
    path("<int:pk>/", views.student_detail, name="detail"),
    path("<int:pk>/edit/", views.student_form, name="edit"),
    path("<int:pk>/status/", views.student_status, name="status"),
    path("<int:pk>/photo/", views.student_photo, name="photo"),
    path("<int:pk>/portal-access/", portal.access, name="portal_access"),
    path("<int:student_pk>/guardians/add/", views.guardian_add, name="guardian_add"),
    path("<int:student_pk>/guardians/new/", views.guardian_link, name="link_create"),
    path("<int:student_pk>/guardians/<int:pk>/edit/", views.guardian_link, name="link_edit"),
    path("<int:student_pk>/guardians/<int:pk>/activate/", views.link_status, {"active": True}, name="link_activate"),
    path("<int:student_pk>/guardians/<int:pk>/deactivate/", views.link_status, {"active": False}, name="link_deactivate"),
    path("<int:student_pk>/enrollments/new/", views.enrollment_create, name="enroll"),
    path("<int:student_pk>/enrollments/<int:pk>/close/", views.enrollment_close, name="enrollment_close"),
]
