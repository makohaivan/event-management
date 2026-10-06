from django.contrib import admin

from .models import Attendance


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("student", "event", "status", "check_in_time", "scanned_by")
    list_filter = ("status", "event")
    search_fields = ("student__username", "event__title")
