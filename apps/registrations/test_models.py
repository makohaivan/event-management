from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.attendance.models import Attendance
from apps.factories import make_event, make_registration, make_user


class RegistrationModelTests(TestCase):
    def test_number_and_token_are_generated_and_unique(self):
        event = make_event()
        first = make_registration(make_user("s1"), event)
        second = make_registration(make_user("s2"), event)
        self.assertTrue(first.registration_number.startswith("REG-"))
        self.assertNotEqual(first.registration_number, second.registration_number)
        self.assertNotEqual(first.qr_token, second.qr_token)

    def test_student_cannot_register_twice_for_same_event(self):
        event = make_event()
        student = make_user("s1")
        make_registration(student, event)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_registration(student, event)

    def test_cancel_sets_status_and_time(self):
        registration = make_registration()
        registration.cancel()
        registration.refresh_from_db()
        self.assertFalse(registration.is_active)
        self.assertIsNotNone(registration.cancelled_at)


class DisplayStatusTests(TestCase):
    def test_registered(self):
        self.assertEqual(make_registration().display_status, "Registered")

    def test_cancelled(self):
        registration = make_registration()
        registration.cancel()
        self.assertEqual(registration.display_status, "Cancelled")

    def test_attended(self):
        registration = make_registration()
        Attendance.objects.create(registration=registration)
        registration.refresh_from_db()
        self.assertEqual(registration.display_status, "Attended")

    def test_absent_when_event_is_over_without_check_in(self):
        registration = make_registration(event=make_event(days_ahead=-1))
        self.assertEqual(registration.display_status, "Absent")
