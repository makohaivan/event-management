from django.core.management.base import BaseCommand

from apps.events.models import Category

DEFAULT_CATEGORIES = [
    "Academic", "Technology", "Sports", "Cultural", "Career", "Entrepreneurship",
    "Religious", "Social", "Workshop", "Seminar", "Conference",
]


class Command(BaseCommand):
    help = "Create the default event categories (safe to run more than once)."

    def handle(self, *args, **options):
        created = 0
        for name in DEFAULT_CATEGORIES:
            _, was_created = Category.objects.get_or_create(name=name)
            created += was_created
        self.stdout.write(self.style.SUCCESS(f"Categories ready ({created} new)."))
