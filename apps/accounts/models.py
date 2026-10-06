from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """One user table for everyone. The `role` field decides what they can do."""

    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        ORGANIZER = "organizer", "Event Organizer"
        ADMIN = "admin", "Administrator"

    email = models.EmailField("email address", unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    phone = models.CharField(max_length=20, blank=True)
    student_number = models.CharField(max_length=30, blank=True)
    faculty = models.CharField(max_length=100, blank=True)
    profile_photo = models.ImageField(upload_to="profiles/", blank=True, null=True)

    def save(self, *args, **kwargs):
        # Superusers created with `createsuperuser` are always administrators
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_organizer(self):
        return self.role == self.Role.ORGANIZER

    @property
    def is_administrator(self):
        return self.role == self.Role.ADMIN

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    def __str__(self):
        return self.display_name
