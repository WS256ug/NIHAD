"""Capture the exact percentage intervals used to grade a report."""
from apps.academics.grading import numeric_intervals
from .formatting import report_number


def grading_key_snapshot(scheme):
    if scheme.mode != 'numeric':
        return []
    return [
        {
            'grade': rule.label,
            'range': f"{report_number(rule.minimum)}-{'<' if upper != 100 else ''}{report_number(upper)}",
        }
        for rule, upper in reversed(list(numeric_intervals(scheme.rules.all())))
    ]
