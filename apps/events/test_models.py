from datetime import time, timedelta

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.events.models import Category, Event
from apps.factories import event_fields, make_event, make_registration, make_user


class CategoryTests(TestCase):
    def test_seed_command_creates_categories_once(self):
        call_command("seed_categories", verbosity=0)
        call_command("seed_categories", verbosity=0)
        self.assertEqual(Category.objects.count(), 11)

    def test_category_name_is_unique(self):
        Category.objects.create(name="Sports")
        with self.assertRaises(Exception):
            Category.objects.create(name="Sports")


class EventValidationTests(TestCase):
    def assertInvalid(self, field, **overrides):
        event = Event(**event_fields(**overrides))
        with self.assertRaises(ValidationError) as ctx:
            event.clean()
        self.assertIn(field, ctx.exception.message_dict)

    def test_valid_event_passes(self):
        Event(**event_fields()).full_clean()

    def test_end_time_must_be_after_start_time(self):
        self.assertInvalid("end_time", end_time=time(9, 0))

    def test_new_event_cannot_be_in_the_past(self):
        self.assertInvalid("event_date", days_ahead=-2)

    def test_deadline_must_be_before_event(self):
        late = timezone.now() + timedelta(days=30)
        self.assertInvalid("registration_deadline", registration_deadline=late)

    def test_capacity_must_be_greater_than_zero(self):
        event = Event(**event_fields(capacity=0))
        with self.assertRaises(ValidationError) as ctx:
            event.full_clean()
        self.assertIn("maximum_capacity", ctx.exception.message_dict)


class EventCapacityTests(TestCase):
    def test_counts_start_at_zero(self):
        event = make_event(capacity=5)
        self.assertEqual(event.registered_count, 0)
        self.assertEqual(event.available_seats, 5)
        self.assertFalse(event.is_full)

    def test_registration_reduces_available_seats(self):
        event = make_event(capacity=5)
        make_registration(make_user("s1"), event)
        make_registration(make_user("s2"), event)
        self.assertEqual(event.registered_count, 2)
        self.assertEqual(event.available_seats, 3)

    def test_event_becomes_full(self):
        event = make_event(capacity=1)
        make_registration(make_user("s1"), event)
        self.assertTrue(event.is_full)
        self.assertEqual(
            event.registration_block_reason(),
            "Registration failed because this event is already full.",
        )

    def test_cancelled_registration_frees_a_seat(self):
        event = make_event(capacity=1)
        registration = make_registration(make_user("s1"), event)
        registration.cancel()
        self.assertFalse(event.is_full)
        self.assertEqual(event.available_seats, 1)


class EventRegistrationRuleTests(TestCase):
    def test_open_for_approved_event_before_deadline(self):
        self.assertTrue(make_event().registration_open)

    def test_closed_after_deadline(self):
        event = make_event(registration_deadline=timezone.now() - timedelta(hours=1))
        self.assertEqual(event.registration_block_reason(), "Registration deadline has passed.")

    def test_closed_when_not_approved(self):
        event = make_event(status=Event.Status.PENDING)
        self.assertFalse(event.registration_open)

    def test_is_over(self):
        self.assertTrue(make_event(days_ahead=-1).is_over)
        self.assertFalse(make_event(days_ahead=3).is_over)
