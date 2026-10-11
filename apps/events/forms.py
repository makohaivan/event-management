from django import forms
from django.db.models import Q
from django.utils import timezone

from apps.accounts.forms import BootstrapFormMixin

from .models import Category, Event


class EventForm(BootstrapFormMixin, forms.ModelForm):
    """Used by organizers. The organizer and status are set by the view, never by the user."""

    class Meta:
        model = Event
        fields = (
            "title", "description", "category", "venue", "event_date", "start_time",
            "end_time", "registration_deadline", "maximum_capacity", "event_image",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "event_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "end_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "registration_deadline": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "maximum_capacity": forms.NumberInput(attrs={"min": 1}),
        }
        help_texts = {
            "registration_deadline": "Students cannot register after this time.",
            "maximum_capacity": "Registration closes automatically when this is reached.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        categories = Category.objects.filter(is_active=True)
        if self.instance.category_id:
            categories = Category.objects.filter(
                Q(is_active=True) | Q(pk=self.instance.category_id)
            )
        self.fields["category"].queryset = categories.order_by("name")
        self.fields["category"].empty_label = "Select a category"
        self.fields["registration_deadline"].input_formats = [
            "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
        ]
        if not self.instance.pk:
            # Front-end hint only; the real check is on the server (Event.clean)
            self.fields["event_date"].widget.attrs["min"] = timezone.localdate().isoformat()

    def clean_event_date(self):
        event_date = self.cleaned_data["event_date"]
        # New events are checked in Event.clean(). Here we only guard edits.
        if self.instance.pk and "event_date" in self.changed_data:
            if event_date < timezone.localdate():
                raise forms.ValidationError("Event date cannot be in the past.")
        return event_date

    def clean_maximum_capacity(self):
        capacity = self.cleaned_data["maximum_capacity"]
        if self.instance.pk:
            current = self.instance.registered_count
            if capacity < current:
                raise forms.ValidationError(
                    f"Capacity cannot be lower than the {current} current registration(s)."
                )
        return capacity


class AdminEventForm(EventForm):
    """Administrators can also choose the organizer and feature the event."""

    class Meta(EventForm.Meta):
        fields = EventForm.Meta.fields + ("organizer", "is_featured")


class RejectionForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(
        label="Reason for rejection",
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="The organizer will see this reason and can fix the event and resubmit it.",
    )


class CategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "description", "is_active")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        duplicates = Category.objects.filter(name__iexact=name).exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError("A category with this name already exists.")
        return name
