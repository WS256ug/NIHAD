"""Use these transactional, authorized services for all student record writes."""
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction

from apps.accounts.models import User
from apps.accounts.permissions import manageable_accounts
from apps.schools.services import lock_school, write_record
from .models import Enrollment, Guardian, Student, StudentGuardian, StudentNumber
from .permissions import can_manage_students


def require_manager(actor):
    if not can_manage_students(actor):
        raise PermissionDenied


def lock_student(pk, school):
    return Student.objects.select_for_update().get(pk=pk, school=school)


def save_student(form, actor):
    require_manager(actor)
    record = form.save(commit=False)
    old_photo = ""
    new_photo = None
    try:
        with transaction.atomic():
            school = lock_school()
            record.school = school
            if record._state.adding:
                counter, _ = StudentNumber.objects.get_or_create(school=school)
                StudentNumber.objects.filter(pk=counter.pk).update(last_value=models.F("last_value") + 1)
                counter.refresh_from_db()
                record.student_id = f"STD-{counter.last_value:06d}"
            else:
                previous = lock_student(record.pk, school)
                record.status = previous.status
                old_photo = previous.photo.name
                if not form.files.get(form.add_prefix("photo")):
                    record.photo = previous.photo
            if form.cleaned_data.get("remove_photo"):
                record.photo = ""
            new_photo = record.photo if record.photo and not record.photo._committed else None
            write_record(record, actor, "Saved student profile.")
            if old_photo and old_photo != record.photo.name:
                storage = Student._meta.get_field("photo").storage
                transaction.on_commit(lambda: storage.delete(old_photo))
        return record
    except Exception:
        # A failed database/audit write must not leave the new private file behind.
        if new_photo and new_photo._committed:
            new_photo.storage.delete(new_photo.name)
        raise


@transaction.atomic
def set_student_status(student, status, actor):
    require_manager(actor)
    school = lock_school()
    student = lock_student(student.pk, school)
    student.status = status
    return write_record(student, actor, f"Changed student status to {status}.", update_fields=["status"])


@transaction.atomic
def register_guardian(form, actor):
    require_manager(actor)
    school = lock_school()
    user = form.save(commit=False)
    user.role = User.Role.GUARDIAN
    user.full_clean()
    user.save()
    LogEntry.objects.create(user=actor, content_type=ContentType.objects.get_for_model(User), object_id=str(user.pk), object_repr=str(user), action_flag=ADDITION, change_message="Registered guardian account.")
    guardian = Guardian(school=school, user=user, phone=form.cleaned_data["phone"], address=form.cleaned_data["address"])
    return write_record(guardian, actor, "Registered guardian profile.")


@transaction.atomic
def save_guardian(form, actor):
    require_manager(actor)
    school = lock_school()
    record = form.save(commit=False)
    if record.school_id != school.pk:
        raise PermissionDenied
    # Lock the account as well: account editing must not race profile creation.
    user = User.objects.select_for_update().get(pk=record.user_id)
    if record._state.adding and not manageable_accounts(actor).filter(pk=user.pk, role=User.Role.GUARDIAN, is_active=True).exists():
        raise ValidationError("Choose an active, ordinary Guardian account.")
    return write_record(record, actor, "Saved guardian contact details.", update_fields=form._meta.fields)


@transaction.atomic
def save_link(form, actor):
    require_manager(actor)
    school = lock_school()
    record = form.save(commit=False)
    lock_student(record.student_id, school)
    if record.pk:
        current = StudentGuardian.objects.select_for_update().get(pk=record.pk, student_id=record.student_id)
        record.is_active = current.is_active
    User.objects.select_for_update().get(pk=record.guardian.user_id)
    return write_record(record, actor, "Saved guardian relationship.", update_fields=form._meta.fields)


@transaction.atomic
def set_link_active(link, active, actor):
    require_manager(actor)
    school = lock_school()
    lock_student(link.student_id, school)
    record = StudentGuardian.objects.select_for_update().get(pk=link.pk, student_id=link.student_id)
    User.objects.select_for_update().get(pk=record.guardian.user_id)
    record.is_active = active
    if not active:
        record.is_primary = False
        record.is_emergency_contact = False
    return write_record(record, actor, "Activated guardian link." if active else "Deactivated guardian link.", update_fields=["is_active", "is_primary", "is_emergency_contact"])


@transaction.atomic
def enroll_student(form, actor):
    require_manager(actor)
    school = lock_school()
    record = form.save(commit=False)
    lock_student(record.student_id, school)
    record.section_id = record.academic_class.section_id
    return write_record(record, actor, "Created enrollment.")


@transaction.atomic
def close_enrollment(enrollment, status, completion_date, actor):
    require_manager(actor)
    school = lock_school()
    lock_student(enrollment.student_id, school)
    record = Enrollment.objects.select_for_update().get(pk=enrollment.pk, student_id=enrollment.student_id)
    if record.status != Enrollment.Status.CURRENT:
        raise ValidationError("This enrollment is already closed.")
    if status == Enrollment.Status.CURRENT:
        raise ValidationError("Choose a completed enrollment status.")
    record.status, record.completion_date = status, completion_date
    return write_record(record, actor, "Closed enrollment; preserved academic context.", update_fields=["status", "completion_date"])
