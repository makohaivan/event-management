from django.test import TestCase

from apps.factories import make_user
from apps.notifications.models import Notification


class NotificationModelTests(TestCase):
    def test_new_notification_is_unread(self):
        note = Notification.objects.create(recipient=make_user(), message="Hello")
        self.assertFalse(note.is_read)
        self.assertEqual(note.notification_type, Notification.Type.GENERAL)

    def test_newest_notification_comes_first(self):
        user = make_user()
        Notification.objects.create(recipient=user, message="first")
        Notification.objects.create(recipient=user, message="second")
        self.assertEqual(user.notifications.first().message, "second")
