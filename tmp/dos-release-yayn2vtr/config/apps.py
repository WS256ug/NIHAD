from django.contrib.admin.apps import AdminConfig


class SchoolAdminConfig(AdminConfig):
    default_site = "config.admin.SchoolAdminSite"
