from django.contrib import admin

from .models import Registration


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ("registration_number", "student", "event", "status", "registered_at")
    list_filter = ("status", "event")
    search_fields = ("registration_number", "student__username", "student__email", "event__title")
    readonly_fields = ("registration_number", "qr_token", "registered_at", "cancelled_at")
