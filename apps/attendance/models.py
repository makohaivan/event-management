from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"

    # OneToOne = at most one attendance record per registration (no duplicates)
    registration = models.OneToOneField(
        "registrations.Registration", on_delete=models.CASCADE, related_name="attendance"
    )
    # student and event are copied from the registration to keep report queries simple
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendance_records"
    )
    event = models.ForeignKey(
        "events.Event", on_delete=models.CASCADE, related_name="attendance_records"
    )
    check_in_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PRESENT)
    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scans_recorded",
    )

    class Meta:
        ordering = ["-check_in_time"]

    def __str__(self):
        return f"{self.student} - {self.event} - {self.get_status_display()}"

    def clean(self):
        if self.registration_id:
            if self.student_id and self.student_id != self.registration.student_id:
                raise ValidationError("Student does not match the registration.")
            if self.event_id and self.event_id != self.registration.event_id:
                raise ValidationError("Event does not match the registration.")

    def save(self, *args, **kwargs):
        if self.registration_id:
            if not self.student_id:
                self.student_id = self.registration.student_id
            if not self.event_id:
                self.event_id = self.registration.event_id
        if self.status == self.Status.PRESENT and self.check_in_time is None:
            self.check_in_time = timezone.now()
        super().save(*args, **kwargs)
