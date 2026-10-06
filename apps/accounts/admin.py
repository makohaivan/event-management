from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User

EXTRA_FIELDS = ("role", "phone", "student_number", "faculty", "profile_photo")


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "role", "is_active")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name", "student_number")
    fieldsets = UserAdmin.fieldsets + (("Role and profile", {"fields": EXTRA_FIELDS}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Role and profile", {"fields": ("email",) + EXTRA_FIELDS}),
    )
