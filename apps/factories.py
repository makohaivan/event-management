"""Small helpers that build test data. Used by every app's tests."""
from datetime import datetime, time, timedelta

from django.utils import timezone

from apps.accounts.models import User
from apps.events.models import Category, Event
from apps.registrations.models import Registration


def make_user(username="student1", role=User.Role.STUDENT, **extra):
    user = User.objects.filter(username=username).first()
    if user:
        return user
    extra.setdefault("email", f"{username}@example.com")
    return User.objects.create_user(username=username, password="pass12345", role=role, **extra)


def make_organizer(username="organizer1"):
    return make_user(username, role=User.Role.ORGANIZER)


def make_category(name="Technology"):
    category, _ = Category.objects.get_or_create(name=name)
    return category


def event_fields(organizer=None, category=None, days_ahead=7, capacity=10,
                 status=Event.Status.APPROVED, **overrides):
    """Valid field values for an Event (not saved)."""
    event_date = timezone.localdate() + timedelta(days=days_ahead)
    start = timezone.make_aware(datetime.combine(event_date, time(10, 0)))
    fields = {
        "title": "Tech Talk",
        "description": "A test event.",
        "category": category or make_category(),
        "organizer": organizer or make_organizer(),
        "venue": "Main Hall",
        "event_date": event_date,
        "start_time": time(10, 0),
        "end_time": time(12, 0),
        "registration_deadline": start - timedelta(days=1),
        "maximum_capacity": capacity,
        "status": status,
    }
    fields.update(overrides)
    return fields


def make_event(**kwargs):
    return Event.objects.create(**event_fields(**kwargs))


def make_registration(student=None, event=None):
    return Registration.objects.create(
        student=student or make_user(), event=event or make_event()
    )
