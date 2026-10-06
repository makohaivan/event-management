from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.attendance.models import Attendance
from apps.factories import make_organizer, make_registration, make_user


class AttendanceModelTests(TestCase):
    def test_student_event_and_time_are_filled_automatically(self):
        registration = make_registration()
        record = Attendance.objects.create(
            registration=registration, scanned_by=make_organizer()
        )
        self.assertEqual(record.student, registration.student)
        self.assertEqual(record.event, registration.event)
        self.assertIsNotNone(record.check_in_time)
        self.assertEqual(record.status, Attendance.Status.PRESENT)

    def test_duplicate_attendance_is_blocked(self):
        registration = make_registration()
        Attendance.objects.create(registration=registration)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Attendance.objects.create(registration=registration)

    def test_student_must_match_registration(self):
        registration = make_registration()
        record = Attendance(
            registration=registration, student=make_user("other"), event=registration.event
        )
        with self.assertRaises(ValidationError):
            record.clean()
