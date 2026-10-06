import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Registration(models.Model):
    class Status(models.TextChoices):
        REGISTERED = "registered", "Registered"
        CANCELLED = "cancelled", "Cancelled"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="registrations"
    )
    event = models.ForeignKey(
        "events.Event", on_delete=models.CASCADE, related_name="registrations"
    )
    registration_number = models.CharField(max_length=20, unique=True, editable=False, blank=True)
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REGISTERED)
    registered_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-registered_at"]
        constraints = [
            # One row per student per event. If a student cancels and registers
            # again later, the same row is re-activated (done in Phase 7).
            models.UniqueConstraint(
                fields=["student", "event"], name="unique_registration_per_student_event"
            ),
        ]

    def __str__(self):
        return f"{self.registration_number} - {self.student} - {self.event}"

    def save(self, *args, **kwargs):
        if not self.registration_number:
            self.registration_number = self._generate_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_number():
        while True:
            number = "REG-" + uuid.uuid4().hex[:8].upper()
            if not Registration.objects.filter(registration_number=number).exists():
                return number

    @property
    def is_active(self):
        return self.status == self.Status.REGISTERED

    def cancel(self):
        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        self.save(update_fields=["status", "cancelled_at"])

    @property
    def display_status(self):
        """Registered / Cancelled / Attended / Absent, worked out from the data."""
        if self.status == self.Status.CANCELLED:
            return "Cancelled"
        record = getattr(self, "attendance", None)
        if record is not None and record.status == "present":
            return "Attended"
        if (record is not None and record.status == "absent") or self.event.is_over:
            return "Absent"
        return "Registered"
