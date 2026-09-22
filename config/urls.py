from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from .health import health

urlpatterns = [
    path('health/', health, name='health'),
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("school/", include("apps.schools.urls")),
    path("students/", include("apps.students.urls")),
    path("academics/", include("apps.academics.urls")),
    path("reports/", include("apps.reports.urls")),
    path("finance/", include("apps.finance.urls")),
    path("expenses/", include("apps.expenses.urls")),
    path("promotions/", include("apps.promotions.urls")),
    path("", include("apps.dashboard.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "NIHAD School Administration"
admin.site.site_title = "NIHAD Administration"
admin.site.index_title = "School administration"
