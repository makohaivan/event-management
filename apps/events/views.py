from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.decorators import admin_required, organizer_required
from apps.registrations.models import Registration

from .forms import AdminEventForm, CategoryForm, EventForm, RejectionForm
from .models import Category, Event
from .utils import paginate


# ---------------------------------------------------------------- helpers
def with_counts(queryset):
    """Add registered_total / registration_total to each event (avoids extra queries)."""
    return queryset.select_related("category", "organizer").annotate(
        registered_total=Count(
            "registrations", filter=Q(registrations__status=Registration.Status.REGISTERED)
        ),
        registration_total=Count("registrations"),
    )


def get_owned_event(request, pk):
    """Organizers may only touch their own events."""
    event = get_object_or_404(Event, pk=pk)
    if event.organizer_id != request.user.pk:
        raise PermissionDenied
    return event


def show_confirm_page(request, title, message, confirm_label, confirm_class, cancel_url):
    return render(request, "events/confirm_action.html", {
        "title": title,
        "message": message,
        "confirm_label": confirm_label,
        "confirm_class": confirm_class,
        "cancel_url": cancel_url,
    })


def filter_events(request, events):
    """Shared search + status filter used by the organizer and admin lists."""
    status = request.GET.get("status", "")
    search = request.GET.get("q", "").strip()
    if status in Event.Status.values:
        events = events.filter(status=status)
    else:
        status = ""
    if search:
        events = events.filter(Q(title__icontains=search) | Q(venue__icontains=search))
    return events, status, search


# ------------------------------------------------------ organizer: pages
@organizer_required
def my_events(request):
    events = with_counts(Event.objects.filter(organizer=request.user))
    events, status, search = filter_events(request, events)
    page_obj, query_string = paginate(request, events.order_by("-event_date", "-start_time"))
    return render(request, "events/organizer_event_list.html", {
        "page_obj": page_obj,
        "query_string": query_string,
        "statuses": Event.Status.choices,
        "selected_status": status,
        "search": search,
    })


@organizer_required
def event_manage_detail(request, pk):
    event = get_owned_event(request, pk)
    return render(request, "events/organizer_event_detail.html", {"event": event})


@organizer_required
def event_create(request):
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.organizer = request.user
            event.status = Event.Status.DRAFT
            event.save()
            messages.success(
                request, "Event saved as a draft. Submit it for approval when you are ready."
            )
            return redirect("events:manage_detail", pk=event.pk)
    else:
        form = EventForm()
    return render(request, "events/event_form.html", {
        "form": form,
        "page_title": "Create event",
        "submit_label": "Save draft",
        "cancel_url": "events:my_events",
    })


@organizer_required
def event_edit(request, pk):
    event = get_owned_event(request, pk)
    if not event.organizer_can_edit:
        messages.error(request, "This event cannot be edited in its current status.")
        return redirect("events:manage_detail", pk=event.pk)
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            # Phase 10: notify registered students when an approved event changes
            messages.success(request, "Event updated.")
            return redirect("events:manage_detail", pk=event.pk)
    else:
        form = EventForm(instance=event)
    return render(request, "events/event_form.html", {
        "form": form,
        "page_title": f"Edit: {event.title}",
        "submit_label": "Save changes",
        "cancel_url": "events:my_events",
    })


@organizer_required
def event_delete(request, pk):
    event = get_owned_event(request, pk)
    if not event.organizer_can_delete:
        messages.error(
            request, "Only draft or rejected events can be deleted. Cancel the event instead."
        )
        return redirect("events:manage_detail", pk=event.pk)
    if request.method == "POST":
        title = event.title
        event.delete()
        messages.success(request, f'"{title}" was deleted.')
        return redirect("events:my_events")
    return show_confirm_page(
        request, "Delete event", f'Delete "{event.title}"? This cannot be undone.',
        "Delete event", "btn-danger", "events:my_events",
    )


@organizer_required
@require_POST
def event_submit(request, pk):
    event = get_owned_event(request, pk)
    if event.can_submit_for_approval:
        event.submit_for_approval()
        messages.success(request, "Event submitted for approval.")
    else:
        messages.error(request, "Only draft or rejected events can be submitted for approval.")
    return redirect("events:manage_detail", pk=event.pk)


@organizer_required
def event_cancel(request, pk):
    event = get_owned_event(request, pk)
    if not event.can_cancel:
        messages.error(request, "Only approved events can be cancelled.")
        return redirect("events:manage_detail", pk=event.pk)
    if request.method == "POST":
        event.cancel()
        # Phase 10: notify registered students that the event was cancelled
        messages.success(request, f'"{event.title}" has been cancelled.')
        return redirect("events:manage_detail", pk=event.pk)
    return show_confirm_page(
        request, "Cancel event",
        f'Cancel "{event.title}"? Registered students will no longer be able to attend.',
        "Cancel event", "btn-danger", "events:manage_detail",
    )


@organizer_required
@require_POST
def event_complete(request, pk):
    event = get_owned_event(request, pk)
    if event.can_complete:
        event.mark_completed()
        messages.success(request, "Event marked as completed.")
    else:
        messages.error(request, "An event can only be completed after it has started.")
    return redirect("events:manage_detail", pk=event.pk)


# --------------------------------------------------------- admin: events
@admin_required
def admin_event_list(request):
    events = with_counts(Event.objects.all())
    events, status, search = filter_events(request, events)
    category = request.GET.get("category", "")
    if category.isdigit():
        events = events.filter(category_id=int(category))
    else:
        category = ""
    page_obj, query_string = paginate(request, events.order_by("-event_date", "-start_time"))
    return render(request, "events/admin_event_list.html", {
        "page_obj": page_obj,
        "query_string": query_string,
        "statuses": Event.Status.choices,
        "categories": Category.objects.all(),
        "selected_status": status,
        "selected_category": category,
        "search": search,
    })


@admin_required
def admin_event_create(request):
    if request.method == "POST":
        form = AdminEventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.status = Event.Status.APPROVED  # administrators approve their own events
            event.save()
            messages.success(request, f'Event "{event.title}" created and approved.')
            return redirect("events:admin_list")
    else:
        form = AdminEventForm()
    return render(request, "events/event_form.html", {
        "form": form,
        "page_title": "Create event (administrator)",
        "submit_label": "Create event",
        "cancel_url": "events:admin_list",
    })


@admin_required
def admin_event_edit(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if request.method == "POST":
        form = AdminEventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, "Event updated.")
            return redirect("events:admin_list")
    else:
        form = AdminEventForm(instance=event)
    return render(request, "events/event_form.html", {
        "form": form,
        "page_title": f"Edit: {event.title}",
        "submit_label": "Save changes",
        "cancel_url": "events:admin_list",
    })


@admin_required
def admin_event_delete(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if event.registrations.exists():
        messages.error(
            request,
            "This event cannot be deleted because students have registered for it. "
            "Cancel the event instead.",
        )
        return redirect("events:admin_list")
    if request.method == "POST":
        title = event.title
        event.delete()
        messages.success(request, f'"{title}" was deleted.')
        return redirect("events:admin_list")
    return show_confirm_page(
        request, "Delete event", f'Delete "{event.title}"? This cannot be undone.',
        "Delete event", "btn-danger", "events:admin_list",
    )


@admin_required
def admin_event_cancel(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if not event.can_cancel:
        messages.error(request, "Only approved events can be cancelled.")
        return redirect("events:admin_list")
    if request.method == "POST":
        event.cancel()
        messages.success(request, f'"{event.title}" has been cancelled.')
        return redirect("events:admin_list")
    return show_confirm_page(
        request, "Cancel event",
        f'Cancel "{event.title}"? Registered students will no longer be able to attend.',
        "Cancel event", "btn-danger", "events:admin_list",
    )


# -------------------------------------------------------- admin: approvals
@admin_required
def event_approvals(request):
    pending = (
        Event.objects.filter(status=Event.Status.PENDING)
        .select_related("category", "organizer")
        .order_by("created_at")
    )
    return render(request, "events/approvals.html", {"events": pending})


@admin_required
@require_POST
def event_approve(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if event.can_be_reviewed:
        event.approve()
        # Phase 10: notify the organizer that the event was approved
        messages.success(request, f'"{event.title}" was approved and is now visible to students.')
    else:
        messages.error(request, "Only events waiting for approval can be approved.")
    return redirect("events:approvals")


@admin_required
def event_reject(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if not event.can_be_reviewed:
        messages.error(request, "Only events waiting for approval can be rejected.")
        return redirect("events:approvals")
    if request.method == "POST":
        form = RejectionForm(request.POST)
        if form.is_valid():
            event.reject(form.cleaned_data["reason"])
            # Phase 10: notify the organizer that the event was rejected
            messages.success(request, f'"{event.title}" was rejected.')
            return redirect("events:approvals")
    else:
        form = RejectionForm()
    return render(request, "events/event_reject.html", {"form": form, "event": event})


# ------------------------------------------------------ admin: categories
@admin_required
def category_list(request):
    categories = Category.objects.annotate(event_total=Count("events"))
    return render(request, "events/category_list.html", {"categories": categories})


@admin_required
def category_create(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Category created.")
            return redirect("events:category_list")
    else:
        form = CategoryForm()
    return render(request, "events/category_form.html", {"form": form, "page_title": "Add category"})


@admin_required
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Category updated.")
            return redirect("events:category_list")
    else:
        form = CategoryForm(instance=category)
    return render(request, "events/category_form.html", {
        "form": form, "page_title": f"Edit category: {category.name}",
    })


@admin_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if category.events.exists():
        messages.error(
            request,
            "This category is used by events and cannot be deleted. "
            "Edit it and untick Active to hide it instead.",
        )
        return redirect("events:category_list")
    if request.method == "POST":
        name = category.name
        category.delete()
        messages.success(request, f'Category "{name}" was deleted.')
        return redirect("events:category_list")
    return show_confirm_page(
        request, "Delete category", f'Delete the category "{category.name}"?',
        "Delete category", "btn-danger", "events:category_list",
    )
