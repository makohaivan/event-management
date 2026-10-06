from django.contrib import admin

from .models import ProblemReport


@admin.register(ProblemReport)
class ProblemReportAdmin(admin.ModelAdmin):
    list_display = ("subject", "reported_by", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("subject", "description", "reported_by__username")
