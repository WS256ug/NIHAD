from django import template
from apps.reports.formatting import report_number

register = template.Library()
register.filter("report_number", report_number)
