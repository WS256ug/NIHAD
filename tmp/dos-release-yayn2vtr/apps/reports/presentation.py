"""Shared display values for the printable report and PDF."""
from decimal import Decimal, InvalidOperation
from .formatting import report_number


def report_summary(data):
    items = []
    if data.get('mode') == 'numeric' and data.get('average') is not None:
        total = report_number(data.get('total'))
        try:
            possible = Decimal(data['maximum_score']) * len(data['subjects'])
            total += ' / ' + report_number(possible)
        except (KeyError, InvalidOperation, TypeError):
            pass
        items += [('Total marks', total), ('Average', report_number(data['average']) + '%')]
    if data.get('aggregate') is not None:
        items += [('Aggregate', str(data['aggregate'])), ('Division', str(data.get('division') or '-'))]
    if data.get('position') is not None:
        items.append(('Position', f"{data['position']} / {data.get('cohort_size', '-')}"))
    return items
