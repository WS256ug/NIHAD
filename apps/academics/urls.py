from django.urls import path
from . import marks, views

app_name = "academics"
urlpatterns = [
    path("", views.overview, name="overview"),
    path("marks-entry/", marks.entry, name="marks_entry"),
    path("assessments/<int:pk>/marks/", marks.roster, name="marks"),
    path("assessments/<int:pk>/marks/<int:subject_pk>/<int:enrollment_pk>/", marks.mark_form, name="mark_form"),
    path("assessments/<int:pk>/open/", marks.assessment_status, {"status": "open"}, name="assessment_open"),
    path("assessments/<int:pk>/close/", marks.assessment_status, {"status": "closed"}, name="assessment_close"),
    path("<slug:kind>/", views.record_list, name="record_list"),
    path("<slug:kind>/new/", views.record_form, name="record_create"),
    path("<slug:kind>/<int:pk>/edit/", views.record_form, name="record_edit"),
    path("<slug:kind>/<int:pk>/activate/", views.record_status, {"active": True}, name="record_activate"),
    path("<slug:kind>/<int:pk>/deactivate/", views.record_status, {"active": False}, name="record_deactivate"),
]
