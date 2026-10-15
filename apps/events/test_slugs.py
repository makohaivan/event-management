from django.test import TestCase
from django.urls import reverse

from apps.events.models import Category
from apps.factories import make_category, make_event


class SlugTests(TestCase):
    def test_slug_is_made_from_the_title(self):
        event = make_event(title="Annual Tech Conference 2026!")
        self.assertEqual(event.slug, "annual-tech-conference-2026")

    def test_duplicate_titles_get_numbered_slugs(self):
        slugs = [make_event(title="Tech Talk").slug for _ in range(3)]
        self.assertEqual(slugs, ["tech-talk", "tech-talk-2", "tech-talk-3"])

    def test_slug_does_not_change_when_the_title_changes(self):
        event = make_event(title="Old name")
        event.title = "Brand new name"
        event.save()
        event.refresh_from_db()
        self.assertEqual(event.slug, "old-name")

    def test_saving_again_keeps_the_same_slug(self):
        event = make_event(title="Stable")
        event.save()
        event.save()
        self.assertEqual(event.slug, "stable")

    def test_reserved_words_are_avoided(self):
        self.assertEqual(make_event(title="Manage").slug, "manage-2")
        self.assertEqual(make_event(title="Admin").slug, "admin-2")

    def test_titles_without_letters_get_a_fallback(self):
        self.assertEqual(make_event(title="!!!").slug, "event")
        self.assertEqual(make_event(title="???").slug, "event-2")

    def test_categories_get_slugs_too(self):
        self.assertEqual(make_category("Career Fair").slug, "career-fair")
        self.assertEqual(Category.objects.create(name="Career  fair!").slug, "career-fair-2")

    def test_event_page_url_uses_the_slug(self):
        make_event(title="Career Fair")
        self.assertEqual(reverse("events:detail", args=["career-fair"]), "/events/career-fair/")
        self.assertEqual(self.client.get("/events/career-fair/").status_code, 200)

    def test_manage_and_admin_routes_are_not_swallowed_by_slugs(self):
        self.assertEqual(reverse("events:my_events"), "/events/manage/")
        response = self.client.get("/events/manage/")
        self.assertEqual(response.status_code, 302)  # sent to log in, not "event not found"
        self.assertEqual(self.client.get("/events/admin/").status_code, 302)
