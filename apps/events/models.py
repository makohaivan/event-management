from datetime import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from .slugs import unique_slug


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True, editable=False)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Category, self.name, "category", self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Event(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending Approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True, editable=False)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="events")
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organized_events",
        limit_choices_to={"role__in": ["organizer", "admin"]},
    )
    venue = models.CharField(max_length=200)
    event_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    registration_deadline = models.DateTimeField()
    maximum_capacity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    event_image = models.ImageField(upload_to="events/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    is_featured = models.BooleanField(default=False)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["event_date", "start_time"]
        indexes = [
            models.Index(fields=["status", "event_date"]),
            models.Index(fields=["title"]),
        ]

    def save(self, *args, **kwargs):
        # The slug is made once, from the first title, so shared links keep working
        if not self.slug:
            self.slug = unique_slug(Event, self.title, "event", self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    # ---- validation (used by forms later through full_clean) ----
    def clean(self):
        errors = {}
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            errors["end_time"] = "End time must be after the start time."
        if self._state.adding and self.event_date and self.event_date < timezone.localdate():
            errors["event_date"] = "Event date cannot be in the past."
        if self.registration_deadline and self.event_date and self.start_time:
            if self.registration_deadline >= self.start_datetime:
                errors["registration_deadline"] = (
                    "Registration deadline must be before the event starts."
                )
        if errors:
            raise ValidationError(errors)

    # ---- time helpers ----
    @property
    def start_datetime(self):
        return timezone.make_aware(datetime.combine(self.event_date, self.start_time))

    @property
    def end_datetime(self):
        return timezone.make_aware(datetime.combine(self.event_date, self.end_time))

    @property
    def is_over(self):
        return timezone.now() > self.end_datetime

    # ---- capacity helpers (computed, never stored) ----
    @property
    def registered_count(self):
        from apps.registrations.models import Registration

        return self.registrations.filter(status=Registration.Status.REGISTERED).count()

    @property
    def available_seats(self):
        return max(self.maximum_capacity - self.registered_count, 0)

    @property
    def is_full(self):
        return self.registered_count >= self.maximum_capacity

    def registration_block_reason(self):
        """Return a user-friendly reason registration is not possible, or None."""
        if self.status != self.Status.APPROVED:
            return "This event is not open for registration."
        if timezone.now() > self.registration_deadline:
            return "Registration deadline has passed."
        if self.is_full:
            return "Registration failed because this event is already full."
        return None

    @property
    def registration_open(self):
        return self.registration_block_reason() is None

    # ---- workflow rules (added in Phase 5) ----
    @property
    def organizer_can_edit(self):
        return self.status in (self.Status.DRAFT, self.Status.REJECTED, self.Status.APPROVED)

    @property
    def organizer_can_delete(self):
        return self.status in (self.Status.DRAFT, self.Status.REJECTED)

    @property
    def can_submit_for_approval(self):
        return self.status in (self.Status.DRAFT, self.Status.REJECTED)

    @property
    def can_be_reviewed(self):
        """Pending events are waiting for an administrator to approve or reject."""
        return self.status == self.Status.PENDING

    @property
    def can_cancel(self):
        return self.status == self.Status.APPROVED

    @property
    def can_complete(self):
        return self.status == self.Status.APPROVED and timezone.now() >= self.start_datetime

    def _change_status(self, allowed, new_status, **extra_fields):
        if not allowed:
            raise ValueError(
                f"An event that is {self.get_status_display().lower()} cannot move to {new_status}."
            )
        self.status = new_status
        for name, value in extra_fields.items():
            setattr(self, name, value)
        self.save(update_fields=["status", "updated_at", *extra_fields])

    def submit_for_approval(self):
        self._change_status(self.can_submit_for_approval, self.Status.PENDING, rejection_reason="")

    def approve(self):
        self._change_status(self.can_be_reviewed, self.Status.APPROVED, rejection_reason="")

    def reject(self, reason):
        self._change_status(self.can_be_reviewed, self.Status.REJECTED, rejection_reason=reason)

    def cancel(self):
        self._change_status(self.can_cancel, self.Status.CANCELLED)

    def mark_completed(self):
        self._change_status(self.can_complete, self.Status.COMPLETED)
