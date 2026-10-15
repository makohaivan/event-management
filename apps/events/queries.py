"""Read-only queries for what students are allowed to see."""
from datetime import date

from django.db.models import Count, F, Q
from django.utils import timezone

from apps.registrations.models import Registration

from .models import Category, Event

# Statuses whose detail page is visible to everyone
PUBLIC_STATUSES = (Event.Status.APPROVED, Event.Status.COMPLETED, Event.Status.CANCELLED)

SORT_OPTIONS = {
    "soonest": ("Soonest first", ("event_date", "start_time")),
    "latest": ("Latest first", ("-event_date", "-start_time")),
    "newest": ("Recently added", ("-created_at",)),
    "title": ("Title A-Z", ("title", "event_date")),
}


def annotate_availability(queryset):
    """Add registered_total and seats_left to each event in one query."""
    return (
        queryset.select_related("category", "organizer")
        .annotate(
            registered_total=Count(
                "registrations",
                filter=Q(registrations__status=Registration.Status.REGISTERED),
            )
        )
        .annotate(seats_left=F("maximum_capacity") - F("registered_total"))
    )


def _upcoming_approved():
    return Event.objects.filter(
        status=Event.Status.APPROVED, event_date__gte=timezone.localdate()
    )


def public_events():
    """Approved events that have not happened yet, soonest first."""
    return annotate_availability(_upcoming_approved()).order_by("event_date", "start_time")


def featured_events():
    return public_events().filter(is_featured=True)


def recently_added_events():
    return public_events().order_by("-created_at")


def venue_choices():
    return (
        _upcoming_approved().order_by("venue").values_list("venue", flat=True).distinct()
    )


def categories_with_counts():
    today = timezone.localdate()
    return (
        Category.objects.filter(is_active=True)
        .annotate(
            upcoming_total=Count(
                "events",
                filter=Q(events__status=Event.Status.APPROVED, events__event_date__gte=today),
            )
        )
        .order_by("name")
    )


def _parse_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def search_public_events(params):
    """
    Apply the search box and filters from request.GET.
    Returns (queryset, cleaned) where `cleaned` holds the values to show back in the form.
    Invalid values are ignored instead of causing errors.
    """
    events = public_events()
    cleaned = {"q": "", "category": "", "venue": "", "date_from": "", "date_to": "", "sort": "soonest"}

    search = params.get("q", "").strip()
    if search:
        events = events.filter(title__icontains=search)
        cleaned["q"] = search

    category = params.get("category", "").strip()
    if category:
        events = events.filter(category__slug=category)
        cleaned["category"] = category

    venue = params.get("venue", "").strip()
    if venue:
        events = events.filter(venue__iexact=venue)
        cleaned["venue"] = venue

    for key, lookup in (("date_from", "event_date__gte"), ("date_to", "event_date__lte")):
        value = _parse_date(params.get(key, ""))
        if value:
            events = events.filter(**{lookup: value})
            cleaned[key] = value.isoformat()

    sort = params.get("sort", "soonest")
    if sort not in SORT_OPTIONS:
        sort = "soonest"
    cleaned["sort"] = sort
    events = events.order_by(*SORT_OPTIONS[sort][1])
    return events, cleaned
