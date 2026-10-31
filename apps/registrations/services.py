"""
The registration rules live here, in one place, so the views stay thin and
every rule can be tested without a browser.
"""
import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.events.models import Event

from .models import Registration


class RegistrationError(Exception):
    """A friendly, user-facing reason why a registration action was refused."""


def register_student(student, event):
    """
    Register `student` for `event` and return the Registration.
    Raises RegistrationError with a friendly message if that is not allowed.
    """
    try:
        with transaction.atomic():
            return _register(student, event)
    except IntegrityError:
        # Two requests arrived at the same moment; the database's unique rule won.
        raise RegistrationError("You are already registered for this event.")


def _register(student, event):
    if not student.is_student:
        raise RegistrationError("Only students can register for events.")

    # Lock the event row so two students cannot both take the last seat.
    # (PostgreSQL honours this lock; SQLite handles one writer at a time anyway.)
    event = Event.objects.select_for_update().get(pk=event.pk)
    existing = Registration.objects.select_for_update().filter(student=student, event=event).first()

    if existing and existing.is_active:
        raise RegistrationError("You are already registered for this event.")

    reason = event.registration_block_reason()
    if reason:
        raise RegistrationError(reason)

    if existing:
        # Registering again after a cancellation: re-activate the same row,
        # keep the registration number, but issue a brand new QR code.
        existing.status = Registration.Status.REGISTERED
        existing.cancelled_at = None
        existing.qr_token = uuid.uuid4()
        existing.registered_at = timezone.now()
        existing.save(update_fields=["status", "cancelled_at", "qr_token", "registered_at"])
        registration = existing
    else:
        registration = Registration.objects.create(student=student, event=event)

    # Phase 10 (notifications): tell the student their registration is confirmed
    # (REGISTRATION_CONFIRMED) and tell the organizer (NEW_REGISTRATION).
    return registration


def cancellation_block_reason(registration):
    """Return a friendly reason this registration cannot be cancelled, or None."""
    if not registration.is_active:
        return "This registration has already been cancelled."
    event = registration.event
    if event.status == Event.Status.CANCELLED:
        return "This event has been cancelled, so there is nothing to cancel."
    if event.status != Event.Status.APPROVED:
        return "This event is no longer open, so the registration cannot be changed."
    if timezone.now() > event.registration_deadline:
        return "Cancellation is only possible until the registration deadline."
    return None


def cancel_registration(registration):
    """Cancel a registration (frees the seat). Raises RegistrationError if not allowed."""
    with transaction.atomic():
        locked = (
            Registration.objects.select_for_update()
            .select_related("event")
            .get(pk=registration.pk)
        )
        reason = cancellation_block_reason(locked)
        if reason:
            raise RegistrationError(reason)
        locked.cancel()
    return locked
