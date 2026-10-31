"""Combine only the two sets belonging to one assessment."""
from decimal import Decimal
from types import SimpleNamespace
from django.core.exceptions import ValidationError
from .grading import calculate_results, rounded


def combined_results(assessment, marks, expected):
    sets = list(assessment.exam_sets.all())
    if [item.number for item in sets] != [1, 2] or assessment.grading_scheme.mode != "numeric":
        raise ValidationError("Two-set reports require Set One, Set Two and numeric grading.")
    if not Decimal("0") < assessment.set_one_weight < Decimal("100"):
        raise ValidationError("Both exam sets must have positive weights totaling 100%.")
    indexed = {(mark.subject_id, mark.exam_set_id): mark for mark in marks}
    required = {(subject, item.pk) for subject in expected for item in sets}
    if not expected or set(indexed) != required:
        raise ValidationError("Complete Set One and Set Two for every assigned subject before generating reports.")
    combined, details = [], {}
    for subject_id in sorted(expected):
        pair = [indexed[subject_id, item.pk] for item in sets]
        absent = any(mark.is_absent for mark in pair)
        if any(mark.score is None and not mark.is_absent for mark in pair):
            raise ValidationError("Enter a numeric result or record absence for each exam set.")
        score = None if absent else rounded(sum((mark.score * item.weight / Decimal("100") for mark, item in zip(pair, sets)), Decimal("0")))
        combined.append(SimpleNamespace(subject_id=subject_id, subject=pair[0].subject, score=score, is_absent=absent, level_id=None))
        details[subject_id] = [{"name": str(item), "score": str(mark.score) if mark.score is not None else None, "absent": mark.is_absent, "weight": str(item.weight)} for mark, item in zip(pair, sets)]
    result = calculate_results(assessment.grading_scheme, combined, assessment.maximum_score)
    result["exam_sets"] = [{"name": str(item), "weight": str(item.weight)} for item in sets]
    for row in result["subjects"]:
        row["exam_sets"] = details[row["subject_id"]]
    return result
