from django.test import TestCase
from django.urls import reverse

from apps.events.models import Category, Event
from apps.factories import (
    make_category, make_event, make_organizer, make_registration, make_user,
)
from apps.factory_forms import valid_event_post_data

S = Event.Status
DENIED = "You do not have permission to perform this action."


class AdminTestCase(TestCase):
    def setUp(self):
        self.admin_user = make_user("adm", role="admin")
        self.organizer = make_organizer("organizer1")
        self.client.login(username="adm", password="pass12345")


class AdminAccessTests(TestCase):
    URLS = ("events:admin_list", "events:approvals", "events:category_list",
            "events:admin_create", "events:category_create")

    def test_anonymous_users_are_sent_to_login(self):
        for name in self.URLS:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_students_and_organizers_are_forbidden(self):
        make_user("stu")
        make_organizer("org")
        for username in ("stu", "org"):
            self.client.login(username=username, password="pass12345")
            for name in self.URLS:
                response = self.client.get(reverse(name))
                self.assertContains(response, DENIED, status_code=403)

    def test_organizer_cannot_approve_own_event(self):
        organizer = make_organizer("org")
        event = make_event(organizer=organizer, status=S.PENDING)
        self.client.login(username="org", password="pass12345")
        response = self.client.post(reverse("events:approve", args=[event.pk]))
        self.assertEqual(response.status_code, 403)
        event.refresh_from_db()
        self.assertEqual(event.status, S.PENDING)


class ApprovalTests(AdminTestCase):
    def test_queue_shows_only_pending_events(self):
        make_event(title="Waiting", status=S.PENDING)
        make_event(title="Already live", status=S.APPROVED)
        make_event(title="Still draft", status=S.DRAFT)
        response = self.client.get(reverse("events:approvals"))
        self.assertContains(response, "Waiting")
        self.assertNotContains(response, "Already live")
        self.assertNotContains(response, "Still draft")

    def test_approve_pending_event(self):
        event = make_event(status=S.PENDING)
        self.client.post(reverse("events:approve", args=[event.pk]))
        event.refresh_from_db()
        self.assertEqual(event.status, S.APPROVED)

    def test_approve_requires_post(self):
        event = make_event(status=S.PENDING)
        response = self.client.get(reverse("events:approve", args=[event.pk]))
        self.assertEqual(response.status_code, 405)

    def test_draft_event_cannot_be_approved(self):
        event = make_event(status=S.DRAFT)
        self.client.post(reverse("events:approve", args=[event.pk]))
        event.refresh_from_db()
        self.assertEqual(event.status, S.DRAFT)

    def test_reject_requires_a_reason(self):
        event = make_event(status=S.PENDING)
        response = self.client.post(reverse("events:reject", args=[event.pk]), {"reason": ""})
        self.assertEqual(response.status_code, 200)
        self.assertIn("reason", response.context["form"].errors)
        event.refresh_from_db()
        self.assertEqual(event.status, S.PENDING)

    def test_reject_with_reason(self):
        event = make_event(status=S.PENDING)
        self.client.post(reverse("events:reject", args=[event.pk]), {"reason": "Missing details."})
        event.refresh_from_db()
        self.assertEqual(event.status, S.REJECTED)
        self.assertEqual(event.rejection_reason, "Missing details.")


class AdminEventTests(AdminTestCase):
    def test_admin_creates_approved_featured_event_for_an_organizer(self):
        data = valid_event_post_data(organizer=self.organizer.pk, is_featured="on")
        response = self.client.post(reverse("events:admin_create"), data)
        self.assertRedirects(response, reverse("events:admin_list"))
        event = Event.objects.get()
        self.assertEqual(event.status, S.APPROVED)
        self.assertEqual(event.organizer, self.organizer)
        self.assertTrue(event.is_featured)

    def test_admin_event_form_applies_validation_rules(self):
        data = valid_event_post_data(organizer=self.organizer.pk, end_time="09:00")
        response = self.client.post(reverse("events:admin_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("end_time", response.context["form"].errors)

    def test_admin_can_edit_any_event(self):
        event = make_event(organizer=self.organizer, title="Original")
        data = valid_event_post_data(organizer=self.organizer.pk, title="Edited by admin")
        self.client.post(reverse("events:admin_edit", args=[event.pk]), data)
        event.refresh_from_db()
        self.assertEqual(event.title, "Edited by admin")

    def test_admin_can_delete_event_without_registrations(self):
        event = make_event()
        self.client.post(reverse("events:admin_delete", args=[event.pk]))
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())

    def test_event_with_registrations_cannot_be_deleted(self):
        event = make_event()
        make_registration(make_user("s1"), event)
        self.client.post(reverse("events:admin_delete", args=[event.pk]))
        self.assertTrue(Event.objects.filter(pk=event.pk).exists())

    def test_admin_can_cancel_approved_event(self):
        event = make_event(status=S.APPROVED)
        self.client.post(reverse("events:admin_cancel", args=[event.pk]))
        event.refresh_from_db()
        self.assertEqual(event.status, S.CANCELLED)

    def test_list_filters(self):
        tech = make_category("Technology")
        sport = make_category("Sports")
        make_event(title="Hack night", category=tech, status=S.APPROVED)
        make_event(title="Football", category=sport, status=S.DRAFT)
        url = reverse("events:admin_list")
        self.assertContains(self.client.get(url, {"status": "draft"}), "Football")
        self.assertNotContains(self.client.get(url, {"status": "draft"}), "Hack night")
        self.assertContains(self.client.get(url, {"category": tech.pk}), "Hack night")
        self.assertNotContains(self.client.get(url, {"category": tech.pk}), "Football")
        self.assertContains(self.client.get(url, {"q": "foot"}), "Football")


class CategoryManagementTests(AdminTestCase):
    def test_create_category(self):
        response = self.client.post(
            reverse("events:category_create"), {"name": "Music", "is_active": "on"}
        )
        self.assertRedirects(response, reverse("events:category_list"))
        self.assertTrue(Category.objects.filter(name="Music").exists())

    def test_duplicate_name_is_rejected_ignoring_case(self):
        make_category("Music")
        response = self.client.post(reverse("events:category_create"), {"name": "music"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["form"].errors)
        self.assertEqual(Category.objects.filter(name__iexact="music").count(), 1)

    def test_edit_and_deactivate_category(self):
        category = make_category("Music")
        self.client.post(
            reverse("events:category_edit", args=[category.pk]), {"name": "Live Music"}
        )
        category.refresh_from_db()
        self.assertEqual(category.name, "Live Music")
        self.assertFalse(category.is_active)

    def test_delete_unused_category(self):
        category = make_category("Unused")
        self.client.post(reverse("events:category_delete", args=[category.pk]))
        self.assertFalse(Category.objects.filter(pk=category.pk).exists())

    def test_category_in_use_cannot_be_deleted(self):
        event = make_event()
        self.client.post(reverse("events:category_delete", args=[event.category.pk]))
        self.assertTrue(Category.objects.filter(pk=event.category.pk).exists())

    def test_list_shows_event_counts(self):
        make_event()
        make_event(title="Second")
        response = self.client.get(reverse("events:category_list"))
        self.assertEqual(response.context["categories"][0].event_total, 2)
