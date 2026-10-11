from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.events.models import Event
from apps.factories import (
    make_category, make_event, make_organizer, make_registration, make_user,
)
from apps.factory_forms import valid_event_post_data

S = Event.Status
DENIED = "You do not have permission to perform this action."


class OrganizerTestCase(TestCase):
    def setUp(self):
        self.organizer = make_organizer("organizer1")
        self.other = make_organizer("organizer2")
        self.client.login(username="organizer1", password="pass12345")

    def own_event(self, **kwargs):
        return make_event(organizer=self.organizer, **kwargs)


class OrganizerAccessTests(TestCase):
    URLS = ("events:my_events", "events:create")

    def test_anonymous_users_are_sent_to_login(self):
        for name in self.URLS:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_students_and_admins_are_forbidden(self):
        make_user("stu")
        make_user("adm", role="admin")
        for username in ("stu", "adm"):
            self.client.login(username=username, password="pass12345")
            for name in self.URLS:
                response = self.client.get(reverse(name))
                self.assertContains(response, DENIED, status_code=403)


class CreateEventTests(OrganizerTestCase):
    def post(self, **overrides):
        return self.client.post(reverse("events:create"), valid_event_post_data(**overrides))

    def test_form_page_loads(self):
        self.assertEqual(self.client.get(reverse("events:create")).status_code, 200)

    def test_valid_event_is_saved_as_draft_for_this_organizer(self):
        response = self.post()
        event = Event.objects.get()
        self.assertRedirects(response, reverse("events:manage_detail", args=[event.pk]))
        self.assertEqual(event.status, S.DRAFT)
        self.assertEqual(event.organizer, self.organizer)

    def test_end_time_before_start_time_is_rejected(self):
        response = self.post(end_time="09:00")
        self.assertEqual(response.status_code, 200)
        self.assertIn("end_time", response.context["form"].errors)
        self.assertEqual(Event.objects.count(), 0)

    def test_past_date_is_rejected(self):
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        response = self.post(event_date=yesterday)
        self.assertIn("event_date", response.context["form"].errors)
        self.assertEqual(Event.objects.count(), 0)

    def test_deadline_after_event_start_is_rejected(self):
        late = (timezone.localdate() + timedelta(days=11)).strftime("%Y-%m-%dT10:00")
        response = self.post(registration_deadline=late)
        self.assertIn("registration_deadline", response.context["form"].errors)

    def test_zero_capacity_is_rejected(self):
        response = self.post(maximum_capacity=0)
        self.assertIn("maximum_capacity", response.context["form"].errors)
        self.assertEqual(Event.objects.count(), 0)

    def test_inactive_category_is_not_accepted(self):
        hidden = make_category("Hidden")
        hidden.is_active = False
        hidden.save()
        response = self.post(category=hidden)
        self.assertIn("category", response.context["form"].errors)

    def test_status_cannot_be_chosen_by_organizer(self):
        self.post(status="approved", organizer=self.other.pk)
        event = Event.objects.get()
        self.assertEqual(event.status, S.DRAFT)
        self.assertEqual(event.organizer, self.organizer)


class MyEventsTests(OrganizerTestCase):
    def test_only_own_events_are_listed(self):
        self.own_event(title="Mine")
        make_event(organizer=self.other, title="Theirs")
        response = self.client.get(reverse("events:my_events"))
        self.assertContains(response, "Mine")
        self.assertNotContains(response, "Theirs")

    def test_status_filter_and_search(self):
        self.own_event(title="Draft talk", status=S.DRAFT)
        self.own_event(title="Live talk", status=S.APPROVED)
        response = self.client.get(reverse("events:my_events"), {"status": "draft"})
        self.assertContains(response, "Draft talk")
        self.assertNotContains(response, "Live talk")
        response = self.client.get(reverse("events:my_events"), {"q": "live"})
        self.assertContains(response, "Live talk")
        self.assertNotContains(response, "Draft talk")

    def test_pagination(self):
        for number in range(12):
            self.own_event(title=f"Event {number:02d}")
        first = self.client.get(reverse("events:my_events"))
        second = self.client.get(reverse("events:my_events"), {"page": 2})
        self.assertEqual(len(first.context["page_obj"]), 10)
        self.assertEqual(len(second.context["page_obj"]), 2)

    def test_registered_count_is_shown(self):
        event = self.own_event(capacity=5)
        make_registration(make_user("s1"), event)
        response = self.client.get(reverse("events:my_events"))
        self.assertContains(response, "1 / 5")


class EditEventTests(OrganizerTestCase):
    def edit(self, event, **overrides):
        return self.client.post(
            reverse("events:edit", args=[event.pk]), valid_event_post_data(**overrides)
        )

    def test_organizer_can_edit_own_draft(self):
        event = self.own_event(status=S.DRAFT)
        self.edit(event, title="New title")
        event.refresh_from_db()
        self.assertEqual(event.title, "New title")

    def test_organizer_can_edit_approved_and_rejected_events(self):
        for status in (S.APPROVED, S.REJECTED):
            event = self.own_event(status=status)
            self.edit(event, title=f"Edited {status}")
            event.refresh_from_db()
            self.assertEqual(event.title, f"Edited {status}")

    def test_cannot_edit_someone_elses_event(self):
        event = make_event(organizer=self.other, title="Original")
        response = self.edit(event, title="Hacked")
        self.assertContains(response, DENIED, status_code=403)
        event.refresh_from_db()
        self.assertEqual(event.title, "Original")

    def test_cannot_edit_pending_event(self):
        event = self.own_event(status=S.PENDING, title="Original")
        response = self.edit(event, title="Changed", )
        self.assertRedirects(response, reverse("events:manage_detail", args=[event.pk]))
        event.refresh_from_db()
        self.assertEqual(event.title, "Original")

    def test_capacity_cannot_drop_below_current_registrations(self):
        event = self.own_event(capacity=10, status=S.APPROVED)
        for name in ("s1", "s2", "s3"):
            make_registration(make_user(name), event)
        response = self.edit(event, maximum_capacity=2)
        self.assertEqual(response.status_code, 200)
        self.assertIn("maximum_capacity", response.context["form"].errors)
        event.refresh_from_db()
        self.assertEqual(event.maximum_capacity, 10)

    def test_edit_page_prefills_values(self):
        event = self.own_event(title="Prefilled")
        response = self.client.get(reverse("events:edit", args=[event.pk]))
        self.assertContains(response, "Prefilled")


class WorkflowActionTests(OrganizerTestCase):
    def test_submit_draft_for_approval(self):
        event = self.own_event(status=S.DRAFT)
        self.client.post(reverse("events:submit", args=[event.pk]))
        event.refresh_from_db()
        self.assertEqual(event.status, S.PENDING)

    def test_submit_requires_post(self):
        event = self.own_event(status=S.DRAFT)
        response = self.client.get(reverse("events:submit", args=[event.pk]))
        self.assertEqual(response.status_code, 405)

    def test_approved_event_cannot_be_submitted_again(self):
        event = self.own_event(status=S.APPROVED)
        self.client.post(reverse("events:submit", args=[event.pk]))
        event.refresh_from_db()
        self.assertEqual(event.status, S.APPROVED)

    def test_cannot_submit_someone_elses_event(self):
        event = make_event(organizer=self.other, status=S.DRAFT)
        response = self.client.post(reverse("events:submit", args=[event.pk]))
        self.assertEqual(response.status_code, 403)
        event.refresh_from_db()
        self.assertEqual(event.status, S.DRAFT)

    def test_rejected_event_can_be_fixed_and_resubmitted(self):
        event = self.own_event(status=S.REJECTED, rejection_reason="Too vague.")
        self.client.post(reverse("events:submit", args=[event.pk]))
        event.refresh_from_db()
        self.assertEqual(event.status, S.PENDING)
        self.assertEqual(event.rejection_reason, "")

    def test_rejection_reason_is_shown_to_organizer(self):
        event = self.own_event(status=S.REJECTED, rejection_reason="Too vague.")
        response = self.client.get(reverse("events:manage_detail", args=[event.pk]))
        self.assertContains(response, "Too vague.")

    def test_delete_draft_event(self):
        event = self.own_event(status=S.DRAFT)
        page = self.client.get(reverse("events:delete", args=[event.pk]))
        self.assertEqual(page.status_code, 200)
        self.client.post(reverse("events:delete", args=[event.pk]))
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())

    def test_approved_event_cannot_be_deleted(self):
        event = self.own_event(status=S.APPROVED)
        self.client.post(reverse("events:delete", args=[event.pk]))
        self.assertTrue(Event.objects.filter(pk=event.pk).exists())

    def test_cannot_delete_someone_elses_event(self):
        event = make_event(organizer=self.other, status=S.DRAFT)
        response = self.client.post(reverse("events:delete", args=[event.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Event.objects.filter(pk=event.pk).exists())

    def test_cancel_approved_event(self):
        event = self.own_event(status=S.APPROVED)
        self.client.post(reverse("events:cancel", args=[event.pk]))
        event.refresh_from_db()
        self.assertEqual(event.status, S.CANCELLED)

    def test_draft_event_cannot_be_cancelled(self):
        event = self.own_event(status=S.DRAFT)
        self.client.post(reverse("events:cancel", args=[event.pk]))
        event.refresh_from_db()
        self.assertEqual(event.status, S.DRAFT)

    def test_complete_started_event(self):
        event = self.own_event(status=S.APPROVED, days_ahead=-1)
        self.client.post(reverse("events:complete", args=[event.pk]))
        event.refresh_from_db()
        self.assertEqual(event.status, S.COMPLETED)

    def test_future_event_cannot_be_completed(self):
        event = self.own_event(status=S.APPROVED, days_ahead=5)
        self.client.post(reverse("events:complete", args=[event.pk]))
        event.refresh_from_db()
        self.assertEqual(event.status, S.APPROVED)
