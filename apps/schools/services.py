"""Validated configuration writes, serialized on the single school row."""
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.accounts.permissions import can_manage_school

from .models import School


def require_manager(actor):
    if not can_manage_school(actor):
        raise PermissionDenied


def lock_school():
    return School.objects.select_for_update().get(pk=1)


def write_record(record, actor, message, update_fields=None):
    creating = record._state.adding
    # Refresh related choices after obtaining the school lock; a parent may have
    # been deactivated since the form was rendered or initially validated.
    record._state.fields_cache.clear()
    record.full_clean()
    if creating:
        record.created_by = actor
    record.updated_by = actor
    record.save(update_fields=None if creating or update_fields is None else [*update_fields, "updated_at", "updated_by"])
    LogEntry.objects.create(
        user=actor, content_type=ContentType.objects.get_for_model(record),
        object_id=str(record.pk), object_repr=str(record),
        action_flag=ADDITION if creating else CHANGE, change_message=message,
    )
    return record


@transaction.atomic
def save_configuration(form, actor):
    require_manager(actor)
    record = form.save(commit=False)
    if isinstance(record, School) and record._state.adding:
        # The fixed primary key rejects concurrent first-time setup.
        return write_record(record, actor, "Created school profile.")
    school = lock_school()
    if isinstance(record, School):
        # Profile edits must not overwrite a period selected in another request.
        record.current_academic_year_id = school.current_academic_year_id
        record.current_term_id = school.current_term_id
    return write_record(record, actor, "Saved configuration fields: " + ", ".join(form.changed_data), update_fields=form._meta.fields)


@transaction.atomic
def set_current_period(actor, academic_year, term):
    require_manager(actor)
    school = lock_school()
    school.current_academic_year_id = academic_year.pk if academic_year else None
    school.current_term_id = term.pk if term else None
    return write_record(school, actor, "Changed current academic period.", update_fields=["current_academic_year", "current_term"])


@transaction.atomic
def set_record_active(record, active, actor):
    require_manager(actor)
    lock_school()
    record = type(record).objects.select_for_update().get(pk=record.pk)
    record.is_active = active
    return write_record(record, actor, "Activated configuration record." if active else "Deactivated configuration record.", update_fields=["is_active"])
