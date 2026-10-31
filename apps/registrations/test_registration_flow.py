from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.events.models import Event
from apps.factories import make_event, make_organizer, make_user
from apps.registrations.models import Registration
from apps.registrations.qr import make_qr_png, qr_payload
from apps.registrations.services import (
    RegistrationError,
    cancel_registration,
    cancellation_block_reason,
    register_student,
)

S = Event.Status
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def login(client, user):
    assert client.login(username=user.username, password="pass12345")


def past_deadline():
    return timezone.now() - timedelta(hours=1)


class RegisterServiceTests(TestCase):
    def setUp(self):
        self.student = make_user("stu")
        self.event = make_event(capacity=2)

    def test_creates_an_active_registration(self):
        registration = register_student(self.student, self.event)
        self.assertTrue(registration.is_active)
        self.assertEqual(registration.student, self.student)
        self.assertTrue(registration.registration_number.startswith("REG-"))
        self.assertEqual(self.event.registered_count, 1)

    def test_duplicate_registration_is_refused(self):
        register_student(self.student, self.event)
        with self.assertRaisesMessage(RegistrationError, "already registered"):
            register_student(self.student, self.event)
        self.assertEqual(Registration.objects.filter(student=self.student).count(), 1)

    def test_full_event_is_refused(self):
        event = make_event(capacity=1)
        register_student(make_user("first"), event)
        with self.assertRaisesMessage(RegistrationError, "already full"):
            register_student(self.student, event)
        self.assertFalse(Registration.objects.filter(student=self.student).exists())

    def test_last_seat_goes_to_the_first_student(self):
        event = make_event(capacity=1)
        register_student(make_user("early"), event)
        with self.assertRaises(RegistrationError):
            register_student(make_user("late"), event)
        self.assertEqual(event.registered_count, 1)

    def test_deadline_passed_is_refused(self):
        event = make_event(registration_deadline=past_deadline())
        with self.assertRaisesMessage(RegistrationError, "deadline"):
            register_student(self.student, event)

    def test_unapproved_events_are_refused(self):
        for status in (S.DRAFT, S.PENDING, S.REJECTED, S.CANCELLED, S.COMPLETED):
            with self.subTest(status=status):
                event = make_event(status=status)
                with self.assertRaisesMessage(RegistrationError, "not open for registration"):
                    register_student(self.student, event)

    def test_only_students_can_register(self):
        for user in (make_organizer("org"), make_user("adm", role=User.Role.ADMIN)):
            with self.subTest(role=user.role):
                with self.assertRaisesMessage(RegistrationError, "Only students"):
                    register_student(user, self.event)

    def test_registering_again_after_cancelling_reuses_the_row(self):
        first = register_student(self.student, self.event)
        old_token, number = first.qr_token, first.registration_number
        cancel_registration(first)
        again = register_student(self.student, self.event)
        self.assertEqual(again.pk, first.pk)
        self.assertEqual(again.registration_number, number)
        self.assertNotEqual(again.qr_token, old_token)
        self.assertTrue(again.is_active)
        self.assertIsNone(again.cancelled_at)
        self.assertEqual(Registration.objects.filter(student=self.student).count(), 1)

    def test_registering_again_is_refused_if_the_event_filled_up(self):
        event = make_event(capacity=1)
        mine = register_student(self.student, event)
        cancel_registration(mine)
        register_student(make_user("other"), event)
        with self.assertRaisesMessage(RegistrationError, "already full"):
            register_student(self.student, event)

    def test_cancelling_frees_the_seat(self):
        event = make_event(capacity=1)
        mine = register_student(self.student, event)
        self.assertEqual(event.registered_count, 1)
        cancel_registration(mine)
        self.assertEqual(event.registered_count, 0)
        register_student(make_user("other"), event)
        self.assertEqual(event.registered_count, 1)


class CancelServiceTests(TestCase):
    def setUp(self):
        self.student = make_user("stu")
        self.event = make_event()
        self.registration = register_student(self.student, self.event)

    def fresh(self):
        return Registration.objects.select_related("event").get(pk=self.registration.pk)

    def test_cancel_before_the_deadline(self):
        cancel_registration(self.registration)
        cancelled = self.fresh()
        self.assertEqual(cancelled.status, Registration.Status.CANCELLED)
        self.assertIsNotNone(cancelled.cancelled_at)

    def test_cancel_after_the_deadline_is_refused(self):
        Event.objects.filter(pk=self.event.pk).update(registration_deadline=past_deadline())
        self.assertIn("deadline", cancellation_block_reason(self.fresh()))
        with self.assertRaisesMessage(RegistrationError, "deadline"):
            cancel_registration(self.registration)
        self.assertTrue(self.fresh().is_active)

    def test_cancelling_twice_is_refused(self):
        cancel_registration(self.registration)
        with self.assertRaisesMessage(RegistrationError, "already been cancelled"):
            cancel_registration(self.registration)

    def test_cancelled_event_cannot_be_cancelled_by_the_student(self):
        Event.objects.filter(pk=self.event.pk).update(status=S.CANCELLED)
        with self.assertRaisesMessage(RegistrationError, "event has been cancelled"):
            cancel_registration(self.registration)


class QrTests(TestCase):
    def test_payload_is_the_secret_token(self):
        registration = register_student(make_user("stu"), make_event())
        self.assertEqual(qr_payload(registration), str(registration.qr_token))

    def test_make_qr_png_returns_a_png(self):
        self.assertTrue(make_qr_png("hello").startswith(PNG_SIGNATURE))


class RegisterViewTests(TestCase):
    def setUp(self):
        self.student = make_user("stu")
        self.event = make_event(title="Career Fair", capacity=2)
        self.url = reverse("registrations:register", args=[self.event.slug])
        login(self.client, self.student)

    def test_url_uses_the_slug(self):
        self.assertEqual(self.url, "/events/career-fair/register/")

    def test_student_can_register_and_sees_the_ticket(self):
        response = self.client.post(self.url, follow=True)
        registration = Registration.objects.get(student=self.student, event=self.event)
        self.assertRedirects(
            response, reverse("registrations:detail", args=[registration.registration_number])
        )
        self.assertContains(response, "You are registered for Career Fair")
        self.assertContains(response, registration.registration_number)
        self.assertContains(response, reverse("registrations:qr", args=[registration.registration_number]))

    def test_registering_needs_a_post_request(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertFalse(Registration.objects.exists())

    def test_anonymous_visitors_are_sent_to_login(self):
        self.client.logout()
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
        self.assertFalse(Registration.objects.exists())

    def test_organizers_and_admins_are_forbidden(self):
        for user in (make_organizer("org"), make_user("adm", role=User.Role.ADMIN)):
            self.client.logout()
            login(self.client, user)
            self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertFalse(Registration.objects.exists())

    def test_double_submit_does_not_create_a_second_registration(self):
        self.client.post(self.url)
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, "already registered")
        self.assertEqual(Registration.objects.filter(student=self.student).count(), 1)

    def test_full_event_shows_the_error_on_the_event_page(self):
        event = make_event(title="Tiny", capacity=1)
        register_student(make_user("other"), event)
        response = self.client.post(reverse("registrations:register", args=[event.slug]), follow=True)
        self.assertContains(response, "already full")
        self.assertFalse(Registration.objects.filter(student=self.student, event=event).exists())

    def test_deadline_passed_shows_the_error(self):
        event = make_event(title="Late", registration_deadline=past_deadline())
        response = self.client.post(reverse("registrations:register", args=[event.slug]), follow=True)
        self.assertContains(response, "Registration deadline has passed.")
        self.assertFalse(Registration.objects.exists())

    def test_unknown_and_unpublished_events_return_404(self):
        draft = make_event(title="Secret", status=S.DRAFT)
        for slug in ("no-such-event", draft.slug):
            response = self.client.post(reverse("registrations:register", args=[slug]))
            self.assertEqual(response.status_code, 404)


class TicketViewTests(TestCase):
    def setUp(self):
        self.student = make_user("stu")
        self.event = make_event(title="Career Fair")
        self.registration = register_student(self.student, self.event)
        self.number = self.registration.registration_number
        self.detail_url = reverse("registrations:detail", args=[self.number])
        self.qr_url = reverse("registrations:qr", args=[self.number])
        login(self.client, self.student)

    def test_owner_sees_the_ticket(self):
        response = self.client.get(self.detail_url)
        self.assertContains(response, self.number)
        self.assertContains(response, "Career Fair")
        self.assertContains(response, self.qr_url)
        self.assertContains(response, "Cancel registration")

    def test_other_students_get_404(self):
        self.client.logout()
        login(self.client, make_user("intruder"))
        self.assertEqual(self.client.get(self.detail_url).status_code, 404)
        self.assertEqual(self.client.get(self.qr_url).status_code, 404)

    def test_anonymous_and_other_roles_cannot_open_it(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.detail_url).status_code, 302)
        self.assertEqual(self.client.get(self.qr_url).status_code, 302)
        login(self.client, make_organizer("org"))
        self.assertEqual(self.client.get(self.detail_url).status_code, 403)

    def test_qr_image_is_a_png(self):
        response = self.client.get(self.qr_url)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertTrue(response.content.startswith(PNG_SIGNATURE))
        self.assertNotIn("attachment", response.get("Content-Disposition", ""))

    def test_qr_download_sets_a_filename(self):
        response = self.client.get(self.qr_url, {"download": "1"})
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(f"ticket-{self.number}.png", response["Content-Disposition"])

    def test_cancelled_registration_has_no_qr_code(self):
        cancel_registration(self.registration)
        self.assertEqual(self.client.get(self.qr_url).status_code, 404)
        response = self.client.get(self.detail_url)
        self.assertContains(response, "This QR code no longer works")
        self.assertNotContains(response, self.qr_url)

    def test_ticket_says_why_cancelling_is_not_possible(self):
        Event.objects.filter(pk=self.event.pk).update(registration_deadline=past_deadline())
        response = self.client.get(self.detail_url)
        self.assertContains(response, "Cancellation is only possible until the registration deadline.")
        self.assertNotContains(response, "Cancel registration")

    def test_cancelled_event_is_announced_on_the_ticket(self):
        Event.objects.filter(pk=self.event.pk).update(status=S.CANCELLED)
        self.assertContains(self.client.get(self.detail_url), "This event has been cancelled.")


class CancelViewTests(TestCase):
    def setUp(self):
        self.student = make_user("stu")
        self.event = make_event(title="Career Fair", capacity=1)
        self.registration = register_student(self.student, self.event)
        self.url = reverse("registrations:cancel", args=[self.registration.registration_number])
        login(self.client, self.student)

    def test_confirmation_page_is_shown(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Cancel your registration?")
        self.registration.refresh_from_db()
        self.assertTrue(self.registration.is_active)

    def test_posting_cancels_and_frees_the_seat(self):
        response = self.client.post(self.url, follow=True)
        self.assertRedirects(response, reverse("registrations:my_registrations"))
        self.assertContains(response, "Your registration for Career Fair was cancelled.")
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.status, Registration.Status.CANCELLED)
        self.assertEqual(self.event.registered_count, 0)

    def test_after_the_deadline_nothing_is_cancelled(self):
        Event.objects.filter(pk=self.event.pk).update(registration_deadline=past_deadline())
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, "Cancellation is only possible until the registration deadline.")
        self.registration.refresh_from_db()
        self.assertTrue(self.registration.is_active)

    def test_confirmation_page_redirects_when_cancelling_is_not_allowed(self):
        cancel_registration(self.registration)
        response = self.client.get(self.url, follow=True)
        self.assertContains(response, "already been cancelled")

    def test_other_students_cannot_cancel_it(self):
        self.client.logout()
        login(self.client, make_user("intruder"))
        self.assertEqual(self.client.post(self.url).status_code, 404)
        self.registration.refresh_from_db()
        self.assertTrue(self.registration.is_active)

    def test_cancelling_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.registration.refresh_from_db()
        self.assertTrue(self.registration.is_active)


class MyRegistrationsTests(TestCase):
    def setUp(self):
        self.student = make_user("stu")
        self.upcoming = make_event(title="Upcoming one", days_ahead=5)
        self.past = make_event(title="Past one", days_ahead=-3)
        self.cancelled_by_me = make_event(title="Cancelled by me", days_ahead=8)
        self.cancelled_event = make_event(title="Called off", days_ahead=9)
        for event in (self.upcoming, self.past, self.cancelled_by_me, self.cancelled_event):
            Registration.objects.create(student=self.student, event=event)
        cancel_registration(Registration.objects.get(student=self.student, event=self.cancelled_by_me))
        Event.objects.filter(pk=self.cancelled_event.pk).update(status=S.CANCELLED)
        # someone else's registration must never show up
        Registration.objects.create(student=make_user("other"), event=make_event(title="Not mine"))
        self.url = reverse("registrations:my_registrations")
        login(self.client, self.student)

    def titles(self, tab=None):
        response = self.client.get(self.url, {"tab": tab} if tab else {})
        self.assertEqual(response.status_code, 200)
        return [row.event.title for row in response.context["registrations"]], response

    def test_upcoming_is_the_default_tab(self):
        titles, response = self.titles()
        self.assertEqual(titles, ["Upcoming one"])
        self.assertEqual(response.context["current_tab"], "upcoming")

    def test_past_tab(self):
        self.assertEqual(self.titles("past")[0], ["Past one"])

    def test_cancelled_tab_includes_cancelled_events(self):
        titles, _ = self.titles("cancelled")
        self.assertEqual(set(titles), {"Cancelled by me", "Called off"})

    def test_all_tab_shows_only_my_registrations(self):
        titles, _ = self.titles("all")
        self.assertEqual(len(titles), 4)
        self.assertNotIn("Not mine", titles)

    def test_tab_counts(self):
        _, response = self.titles()
        counts = {key: count for key, _, count in response.context["tabs"]}
        self.assertEqual(counts, {"upcoming": 1, "past": 1, "cancelled": 2, "all": 4})

    def test_unknown_tab_falls_back_to_upcoming(self):
        self.assertEqual(self.titles("nonsense")[0], ["Upcoming one"])

    def test_rows_know_whether_they_can_be_cancelled(self):
        _, response = self.titles()
        self.assertTrue(response.context["registrations"][0].can_cancel)
        self.assertContains(response, "Cancel</a>")

    def test_event_cancelled_badge(self):
        _, response = self.titles("cancelled")
        self.assertContains(response, "Event cancelled")

    def test_pagination_keeps_the_tab(self):
        for number in range(11):
            Registration.objects.create(
                student=self.student, event=make_event(title=f"Extra {number}", days_ahead=2)
            )
        # 12 upcoming registrations in total: 10 on page 1, 2 on page 2
        response = self.client.get(self.url, {"tab": "upcoming"})
        self.assertEqual(len(response.context["registrations"]), 10)
        self.assertContains(response, "tab=upcoming&page=2")
        second = self.client.get(self.url, {"tab": "upcoming", "page": 2})
        self.assertEqual(len(second.context["registrations"]), 2)
        # with no ?tab= at all, the default (upcoming) tab still paginates correctly
        default_second = self.client.get(self.url, {"page": 2})
        self.assertEqual(len(default_second.context["registrations"]), 2)

    def test_empty_state(self):
        self.client.logout()
        login(self.client, make_user("newbie"))
        self.assertContains(self.client.get(self.url), "You have no upcoming registrations.")

    def test_login_and_role_are_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        login(self.client, make_organizer("org"))
        self.assertEqual(self.client.get(self.url).status_code, 403)


class EventPageIntegrationTests(TestCase):
    def setUp(self):
        self.student = make_user("stu")
        self.event = make_event(title="Career Fair", capacity=1)
        self.url = reverse("events:detail", args=[self.event.slug])
        self.register_url = reverse("registrations:register", args=[self.event.slug])

    def test_student_sees_a_register_button(self):
        login(self.client, self.student)
        response = self.client.get(self.url)
        self.assertContains(response, "Register now")
        self.assertContains(response, self.register_url)

    def test_registered_student_sees_ticket_link_instead(self):
        login(self.client, self.student)
        registration = register_student(self.student, self.event)
        response = self.client.get(self.url)
        self.assertContains(response, "You are registered for this event.")
        self.assertContains(response, reverse("registrations:detail", args=[registration.registration_number]))
        self.assertNotContains(response, "Register now")

    def test_registered_student_still_sees_ticket_when_event_is_full(self):
        login(self.client, self.student)
        register_student(self.student, self.event)
        self.assertContains(self.client.get(self.url), "You are registered for this event.")

    def test_after_cancelling_the_button_says_register_again(self):
        login(self.client, self.student)
        registration = register_student(self.student, self.event)
        cancel_registration(registration)
        self.assertContains(self.client.get(self.url), "Register again")

    def test_full_event_has_no_register_button_for_other_students(self):
        register_student(make_user("first"), self.event)
        login(self.client, self.student)
        response = self.client.get(self.url)
        self.assertContains(response, "Registration Full")
        self.assertNotContains(response, "Register now")

    def test_anonymous_visitor_is_asked_to_log_in(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Log in to register")
        self.assertNotContains(response, "Register now")

    def test_organizer_is_told_only_students_can_register(self):
        login(self.client, make_organizer("org"))
        response = self.client.get(self.url)
        self.assertContains(response, "Only student accounts can register for events.")
        self.assertNotContains(response, "Register now")

    def test_navbar_link_is_for_students_only(self):
        login(self.client, self.student)
        self.assertContains(self.client.get(reverse("home")), "My Registrations")
        self.client.logout()
        login(self.client, make_organizer("org"))
        self.assertNotContains(self.client.get(reverse("home")), "My Registrations")
        self.client.logout()
        self.assertNotContains(self.client.get(reverse("home")), "My Registrations")
