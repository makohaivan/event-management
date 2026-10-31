from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.registrations.models import Registration

from .models import Category, Event
from .queries import (
    PUBLIC_STATUSES,
    SORT_OPTIONS,
    annotate_availability,
    categories_with_counts,
    featured_events,
    public_events,
    recently_added_events,
    search_public_events,
    venue_choices,
)
from .utils import paginate


def home(request):
    return render(request, "home.html", {
        "featured_events": featured_events()[:3],
        "upcoming_events": public_events()[:6],
        "recent_events": recently_added_events()[:6],
        "categories": categories_with_counts(),
    })


def event_list(request):
    events, filters = search_public_events(request.GET)
    page_obj, query_string = paginate(request, events, per_page=9)
    has_filters = any(filters[key] for key in ("q", "category", "venue", "date_from", "date_to"))
    return render(request, "events/event_list.html", {
        "page_obj": page_obj,
        "query_string": query_string,
        "filters": filters,
        "has_filters": has_filters,
        "categories": Category.objects.filter(is_active=True).order_by("name"),
        "venues": venue_choices(),
        "sort_options": [(key, label) for key, (label, _) in SORT_OPTIONS.items()],
    })


def event_detail(request, slug):
    event = get_object_or_404(annotate_availability(Event.objects.all()), slug=slug)

    previewing = False
    if event.status not in PUBLIC_STATUSES:
        user = request.user
        can_preview = user.is_authenticated and (
            user.pk == event.organizer_id or user.is_administrator
        )
        if not can_preview:
            raise Http404("Event not found")
        previewing = True

    now = timezone.now()
    if event.status != Event.Status.APPROVED or event.is_over:
        registration_state = "unavailable"
    elif now > event.registration_deadline:
        registration_state = "closed"
    elif event.seats_left <= 0:
        registration_state = "full"
    else:
        registration_state = "open"

    capacity = event.maximum_capacity
    percent_full = min(100, round(event.registered_total * 100 / capacity)) if capacity else 0
    related_events = public_events().filter(category=event.category).exclude(pk=event.pk)[:3]

    my_registration = None
    if request.user.is_authenticated and request.user.is_student:
        my_registration = Registration.objects.filter(student=request.user, event=event).first()

    return render(request, "events/event_detail.html", {
        "event": event,
        "my_registration": my_registration,
        "previewing": previewing,
        "registration_state": registration_state,
        "percent_full": percent_full,
        "related_events": related_events,
    })
