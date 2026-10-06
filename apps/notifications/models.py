from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        REGISTRATION_CONFIRMED = "registration_confirmed", "Registration confirmed"
        EVENT_CANCELLED = "event_cancelled", "Event cancelled"
        EVENT_UPDATED = "event_updated", "Event updated"
        EVENT_REMINDER = "event_reminder", "Event reminder"
        EVENT_APPROVED = "event_approved", "Event approved"
        EVENT_REJECTED = "event_rejected", "Event rejected"
        NEW_REGISTRATION = "new_registration", "New registration"
        GENERAL = "general", "General"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    notification_type = models.CharField(
        max_length=30, choices=Type.choices, default=Type.GENERAL
    )
    message = models.CharField(max_length=255)
    related_event = models.ForeignKey(
        "events.Event", on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications"
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self):
        return f"To {self.recipient}: {self.message[:50]}"
