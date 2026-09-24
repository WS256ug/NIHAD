"""Render numeric inputs without unnecessary decimal zeros."""
from django.forms.renderers import DjangoTemplates
from apps.reports.formatting import report_number


class CompactNumberRenderer(DjangoTemplates):
    def render(self, template_name, context, request=None):
        if template_name == "django/forms/widgets/number.html":
            widget = context["widget"]
            value = widget.get("value")
            if value not in (None, ""):
                context = {**context, "widget": {**widget, "value": report_number(value)}}
        return super().render(template_name, context, request=request)
