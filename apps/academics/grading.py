"""Deterministic Decimal calculations; report generation snapshots the output."""
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError


def rounded(value):
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def grade_score(score, maximum, rules):
    if maximum <= 0 or not Decimal('0') <= score <= maximum:
        raise ValidationError('Score is outside the assessment range.')
    percentage = score * Decimal('100') / maximum
    for rule in rules:
        if rule.minimum <= percentage < rule.maximum or percentage == rule.maximum == Decimal('100'):
            return percentage, rule
    raise ValidationError('No grade rule covers this score. Review the grading configuration.')


def calculate_results(scheme, marks, maximum):
    scheme.validate_configuration()
    marks = list(marks)
    if not scheme.is_active or not marks:
        raise ValidationError('An active grading scheme and completed marks are required.')
    rules = list(scheme.rules.all())
    subjects = []
    for mark in marks:
        row = {'subject_id': mark.subject_id, 'subject': mark.subject.name, 'code': mark.subject.code}
        if scheme.mode == 'descriptive':
            if not mark.level_id or mark.level.scheme_id != scheme.pk:
                raise ValidationError('Every learning area needs a level from the selected scheme.')
            row.update(score=None, percentage=None, grade=mark.level.label, points=None)
        else:
            if mark.score is None:
                raise ValidationError('Every numeric subject needs a score.')
            percentage, rule = grade_score(mark.score, maximum, rules)
            row.update(score=str(mark.score), percentage=str(rounded(percentage)), grade=rule.label, points=rule.points)
        subjects.append(row)
    result = {'mode': scheme.mode, 'scheme': scheme.name, 'subjects': subjects, 'total': None, 'average': None, 'aggregate': None, 'division': None, 'aggregate_subjects': []}
    if scheme.mode == 'descriptive':
        return result
    total = sum((mark.score for mark in marks), Decimal('0'))
    result.update(total=str(rounded(total)), average=str(rounded(total * 100 / (maximum * len(marks)))))
    if scheme.aggregate_mode == 'none':
        return result
    required = set(scheme.required_subjects.values_list('pk', flat=True))
    available = {row['subject_id'] for row in subjects}
    if not required <= available:
        raise ValidationError('Marks for required aggregate subjects are missing.')
    selected = [row for row in subjects if row['subject_id'] in required]
    if scheme.aggregate_mode == 'all':
        selected = subjects
    elif scheme.aggregate_mode == 'best':
        if len(subjects) < scheme.best_n:
            raise ValidationError('Too few graded subjects for the configured best N aggregate.')
        others = sorted((row for row in subjects if row['subject_id'] not in required), key=lambda row: (row['points'], -Decimal(row['percentage']), row['subject_id']))
        selected += others[:scheme.best_n - len(selected)]
    aggregate = sum(row['points'] for row in selected)
    division = next((rule.label for rule in scheme.divisions.all() if rule.minimum <= aggregate <= rule.maximum), 'Unclassified')
    result.update(aggregate=aggregate, division=division, aggregate_subjects=[row['subject_id'] for row in selected])
    return result


def competition_positions(results):
    """Equal averages share a position; the next position skips tied students."""
    ordered = sorted(results.items(), key=lambda item: (-Decimal(item[1]['average']), item[0]))
    positions, previous, position = {}, None, 0
    for index, (key, result) in enumerate(ordered, 1):
        average = Decimal(result['average'])
        if average != previous:
            position = index
        positions[key] = position
        previous = average
    return positions
