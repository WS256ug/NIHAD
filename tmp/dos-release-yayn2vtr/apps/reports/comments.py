"""Shared class-teacher and headteacher suggestions based on snapshotted results."""
from decimal import Decimal, InvalidOperation
from hashlib import sha256


COMMENTS = {
    'outstanding': (
        'Gorgeous performance.',
        'Outstanding results.',
        'Keep it up, dear.',
        'Excellent results.',
        'Marvellous performance.',
    ),
    'moderate': (
        'A good report seen.',
        'Can do better than this.',
        'Learner exhibits good performance.',
    ),
    'low': (
        'Double your efforts, dear.',
        'More effort needed.',
        'Try harder next time.',
    ),
}


def suggest_headteacher_comment(snapshot, school, *, assessment_id, enrollment_id):
    """Return auditable suggestion metadata; never treat absence as low performance."""
    if snapshot.get('mode') != 'numeric' or snapshot.get('has_absences'):
        return None
    if any(row.get('absent') for row in snapshot.get('subjects', [])):
        return None
    try:
        average = Decimal(str(snapshot.get('average')))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not average.is_finite() or not 0 <= average <= 100:
        return None
    if average >= school.headteacher_outstanding_min:
        band = 'outstanding'
    elif average >= school.headteacher_moderate_min:
        band = 'moderate'
    else:
        band = 'low'
    options = COMMENTS[band]
    key = f'{assessment_id}:{enrollment_id}:{band}'.encode()
    comment = options[int.from_bytes(sha256(key).digest()[:8], 'big') % len(options)]
    return {
        'band': band, 'average': str(average), 'comment': comment,
        'outstanding_min': str(school.headteacher_outstanding_min),
        'moderate_min': str(school.headteacher_moderate_min),
    }
