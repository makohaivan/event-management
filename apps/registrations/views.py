from django.contrib import messages
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.accounts.decorators import student_required
from apps.events.models import Event
from apps.events.queries import PUBLIC_STATUSES
from apps.events.utils import paginate

from .models import Registration
from .qr import make_qr_png, qr_payload
from .services import (
    RegistrationError,
    cancel_registration,
    cancellation_block_reason,
    register_student,
)

TABS = [("upcoming", "Upcoming"), ("past", "Past"), ("cancelled", "Cancelled"), ("all", "All")]


def _own_registrations(user):
    return Registration.objects.filter(student=user).select_related(
        "event", "event__category", "attendance"
    )


def _own_registration_or_404(user, number):
    return get_object_or_404(
        Registration.objects.select_related("event", "event__category", "event__organizer"),
        registration_number=number,
        student=user,
    )


@student_required
@require_POST
def register(request, slug):
    event = get_object_or_404(Event, slug=slug, status__in=PUBLIC_STATUSES)
    try:
        registration = register_student(request.user, event)
    except RegistrationError as error:
        messages.error(request, str(error))
        return redirect("events:detail", slug=event.slug)
    messages.success(request, f"You are registered for {event.title}. Your QR ticket is below.")
    return redirect("registrations:detail", number=registration.registration_number)


@student_required
def registration_detail(request, number):
    registration = _own_registration_or_404(request.user, number)
    reason = cancellation_block_reason(registration)
    return render(request, "registrations/registration_detail.html", {
        "registration": registration,
        "event": registration.event,
        "can_cancel": reason is None,
        "cancel_reason": reason if registration.is_active else "",
    })


@student_required
@never_cache
def qr_image(request, number):
    registration = _own_registration_or_404(request.user, number)
    if not registration.is_active:
        raise Http404("No QR code for a cancelled registration")
    response = HttpResponse(make_qr_png(qr_payload(registration)), content_type="image/png")
    if request.GET.get("download"):
        response["Content-Disposition"] = f'attachment; filename="ticket-{registration.registration_number}.png"'
    return response


@student_required
def my_registrations(request):
    today = timezone.localdate()
    cancelled = Q(status=Registration.Status.CANCELLED) | Q(event__status=Event.Status.CANCELLED)
    active = Q(status=Registration.Status.REGISTERED)
    filters = {
        "upcoming": active & Q(event__status=Event.Status.APPROVED, event__event_date__gte=today),
        "past": active
        & ~Q(event__status=Event.Status.CANCELLED)
        & (Q(event__event_date__lt=today) | Q(event__status=Event.Status.COMPLETED)),
        "cancelled": cancelled,
        "all": Q(),
    }
    orderings = {
        "upcoming": ("event__event_date", "event__start_time"),
        "past": ("-event__event_date", "-event__start_time"),
        "cancelled": ("-registered_at",),
        "all": ("-registered_at",),
    }

    current_tab = request.GET.get("tab", "upcoming")
    if current_tab not in filters:
        current_tab = "upcoming"

    base = _own_registrations(request.user)
    tabs = [(key, label, base.filter(filters[key]).count()) for key, label in TABS]

    queryset = base.filter(filters[current_tab]).order_by(*orderings[current_tab])
    page_obj, query_string = paginate(request, queryset, per_page=10)
    rows = list(page_obj.object_list)
    for row in rows:
        row.can_cancel = cancellation_block_reason(row) is None

    return render(request, "registrations/my_registrations.html", {
        "registrations": rows,
        "page_obj": page_obj,
        "query_string": query_string,
        "tabs": tabs,
        "current_tab": current_tab,
    })


@student_required
def cancel(request, number):
    registration = _own_registration_or_404(request.user, number)

    if request.method == "POST":
        try:
            cancel_registration(registration)
        except RegistrationError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, f"Your registration for {registration.event.title} was cancelled.")
        return redirect("registrations:my_registrations")

    reason = cancellation_block_reason(registration)
    if reason:
        messages.error(request, reason)
        return redirect("registrations:detail", number=registration.registration_number)
    return render(request, "registrations/cancel_confirm.html", {
        "registration": registration,
        "event": registration.event,
    })
