"""Section-based grade setup with automatic, historically safe versions."""
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import OuterRef, Subquery

from apps.schools.services import lock_school, write_record
from .models import DivisionRule, GradeRule, GradingScheme


def current_scheme(section):
    # Newest configuration is authoritative, including incomplete setup.
    return GradingScheme.objects.filter(section=section).order_by("-pk").first()


def current_rules(queryset):
    latest = GradingScheme.objects.filter(section_id=OuterRef("scheme__section_id")).order_by("-pk")
    return queryset.filter(scheme_id=Subquery(latest.values("pk")[:1]))


def assessment_grades(section, actor=None):
    scheme = current_scheme(section)
    if scheme and not scheme.is_active and actor and scheme.mode == "numeric" and not scheme.in_use():
        from .grading import numeric_intervals
        rules = list(scheme.rules.all())
        # Repair readiness for saved integer bands previously rejected as gaps.
        if rules and any(upper != rule.maximum for rule, upper in numeric_intervals(rules)):
            scheme.validate_configuration()
            scheme.is_active = True
            write_record(scheme, actor, "Grades ready: consecutive whole-number ranges include decimal marks.", update_fields=["is_active"])
    if not scheme or not scheme.is_active:
        raise ValidationError(f"Finish adding grades for {section.name} in Academics → Grades before generating reports.")
    scheme.validate_configuration()
    return scheme


def copy_scheme(source, actor):
    target = write_record(GradingScheme(
        section=source.section, name=f"Section grades {uuid4().hex[:12]}", mode=source.mode,
        aggregate_mode=source.aggregate_mode, best_n=source.best_n,
    ), actor, "Created a new grade version; earlier assessments retain their grades.")
    target.required_subjects.set(source.required_subjects.all())
    copies = {}
    for model, relation, fields in (
        (GradeRule, "rules", ("label", "minimum", "maximum", "points", "sort_order")),
        (DivisionRule, "divisions", ("label", "minimum", "maximum")),
    ):
        for rule in getattr(source, relation).all():
            copy = write_record(model(scheme=target, **{field: getattr(rule, field) for field in fields}), actor, "Copied historical grading configuration.")
            copies[(model, rule.pk)] = copy
    return target, copies


@transaction.atomic
def save_section_rule(form, actor):
    from .services import require_manager

    require_manager(actor)
    lock_school()
    section = form.cleaned_data["section"]
    if not type(section).objects.filter(pk=section.pk, school_id=1, is_active=True).exists():
        raise ValidationError("Choose an active school section.")
    source = current_scheme(section)
    original = form.instance
    if original and original.pk and (not source or original.scheme_id != source.pk):
        raise ValidationError("These grades have changed. Close this form and reopen the latest grade.")
    model = form.rule_model
    mode = form.cleaned_data.get("mode", "numeric")
    if source and source.mode != mode:
        raise ValidationError("Use the same grade type as the other grades in this section: mark ranges for numeric grades, or labels only for learning levels.")
    if model == DivisionRule and not source:
        raise ValidationError("Add this section's grades before adding divisions.")
    target = source
    record = original
    if source and (source.is_active or source.in_use() or source.assessments.exists()):
        target, copies = copy_scheme(source, actor)
        record = copies.get((model, original.pk)) if original and original.pk else None
    elif not source:
        target = write_record(GradingScheme(section=section, name=f"Section grades {uuid4().hex[:12]}", mode=mode), actor, "Started section grades.")
    if model == DivisionRule and target.aggregate_mode == "none":
        if target.rules.filter(points__isnull=True).exists():
            raise ValidationError("Add points to every grade before creating divisions.")
        target.aggregate_mode = "all"
        target = write_record(target, actor, "Enabled aggregation of all subjects for section divisions.")
    record = record or model(scheme=target)
    for field in form.rule_fields:
        setattr(record, field, form.cleaned_data[field])
    record = write_record(record, actor, "Saved section grade configuration.")
    try:
        target.validate_configuration()
    except ValidationError:
        # Partial grade ranges can be saved, but cannot be used by new assessments.
        ready = False
    else:
        ready = True
    target.is_active = ready
    write_record(target, actor, "Grades ready for assessments." if ready else "Grade setup is incomplete.", update_fields=["is_active"])
    return record
