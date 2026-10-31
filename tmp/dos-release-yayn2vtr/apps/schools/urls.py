from django.urls import path

from . import views

app_name = "schools"
urlpatterns = [
    path("", views.overview, name="overview"),
    path("profile/", views.profile, name="profile"),
    path("current-period/", views.current_period, name="current_period"),
    path("term-options/", views.term_options, name="term_options"),
    path("<slug:kind>/", views.record_list, name="record_list"),
    path("<slug:kind>/new/", views.record_form, name="record_create"),
    path("<slug:kind>/<int:pk>/edit/", views.record_form, name="record_edit"),
    path("<slug:kind>/<int:pk>/activate/", views.record_status, {"activate": True}, name="record_activate"),
    path("<slug:kind>/<int:pk>/deactivate/", views.record_status, {"activate": False}, name="record_deactivate"),
]
