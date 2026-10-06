from django.contrib import admin

from .models import Category, Event


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "organizer", "event_date", "status", "registered", "maximum_capacity")
    list_filter = ("status", "category", "is_featured")
    search_fields = ("title", "venue", "organizer__username")
    date_hierarchy = "event_date"

    @admin.display(description="Registered")
    def registered(self, obj):
        return obj.registered_count
