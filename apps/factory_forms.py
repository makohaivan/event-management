"""Form data for view tests (kept next to factories.py)."""
from datetime import timedelta

from django.utils import timezone

from apps.factories import make_category


def valid_event_post_data(category=None, **overrides):
    category = category or make_category()
    today = timezone.localdate()
    data = {
        "title": "Career Fair",
        "description": "Meet employers.",
        "category": category.pk,
        "venue": "Main Hall",
        "event_date": (today + timedelta(days=10)).isoformat(),
        "start_time": "10:00",
        "end_time": "12:00",
        "registration_deadline": (today + timedelta(days=8)).strftime("%Y-%m-%dT10:00"),
        "maximum_capacity": 50,
    }
    data.update(overrides)
    return data
