from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.events.models import Category, Event

# title, category, venue, days from today, start, end, capacity, featured
DEMO_EVENTS = [
    ("Career Fair", "Career", "Main Hall", 5, (9, 0), (16, 0), 300, True),
    ("Intro to Django Workshop", "Workshop", "Innovation Lab", 3, (14, 0), (17, 0), 40, False),
    ("Inter-Faculty Football Final", "Sports", "Sports Ground", 7, (16, 0), (18, 0), 500, True),
    ("Cultural Night", "Cultural", "Freedom Square", 12, (18, 0), (22, 0), 400, True),
    ("Startup Pitch Day", "Entrepreneurship", "Innovation Lab", 9, (10, 0), (15, 0), 80, False),
    ("AI and Society Seminar", "Seminar", "Auditorium", 6, (11, 0), (13, 0), 150, False),
    ("Research Methods Lecture", "Academic", "Lecture Hall B", 4, (8, 0), (10, 0), 120, False),
    ("Interfaith Prayer Breakfast", "Religious", "Chapel", 14, (7, 0), (9, 0), 100, False),
    ("Freshers Social Mixer", "Social", "Student Centre", 2, (17, 0), (20, 0), 200, False),
    ("Annual Tech Conference", "Conference", "Auditorium", 20, (9, 0), (17, 0), 600, False),
    ("Cybersecurity Awareness Talk", "Technology", "Innovation Lab", 10, (15, 0), (16, 30), 60, False),
    ("Public Speaking Workshop", "Workshop", "Lecture Hall B", 16, (14, 0), (16, 0), 30, False),
    ("Women in Tech Panel", "Technology", "Auditorium", 25, (14, 0), (16, 0), 150, False),
]


class Command(BaseCommand):
    help = "Create sample approved events for demos (safe to run more than once)."

    def handle(self, *args, **options):
        organizer, created = User.objects.get_or_create(
            username="demo_organizer",
            defaults={
                "email": "demo.organizer@example.com",
                "first_name": "Demo",
                "last_name": "Organizer",
                "role": User.Role.ORGANIZER,
            },
        )
        if created:
            organizer.set_password("demo12345")
            organizer.save()

        today = timezone.localdate()
        new_events = 0
        for title, category_name, venue, days, start, end, capacity, featured in DEMO_EVENTS:
            category, _ = Category.objects.get_or_create(name=category_name)
            event_date = today + timedelta(days=days)
            start_time, end_time = time(*start), time(*end)
            deadline = timezone.make_aware(datetime.combine(event_date, start_time)) - timedelta(hours=12)
            _, was_created = Event.objects.get_or_create(
                title=title,
                defaults={
                    "description": f"{title} - a sample event for demonstrating the system.\n\n"
                                   "Meet students and staff, learn something new and enjoy the day.",
                    "category": category,
                    "organizer": organizer,
                    "venue": venue,
                    "event_date": event_date,
                    "start_time": start_time,
                    "end_time": end_time,
                    "registration_deadline": deadline,
                    "maximum_capacity": capacity,
                    "status": Event.Status.APPROVED,
                    "is_featured": featured,
                },
            )
            new_events += was_created

        self.stdout.write(self.style.SUCCESS(f"Demo events ready ({new_events} new)."))
        if created:
            self.stdout.write("Demo organizer login: demo_organizer / demo12345")
