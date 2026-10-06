from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User
from apps.factories import make_user


class UserModelTests(TestCase):
    def test_default_role_is_student(self):
        user = make_user("ivan")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertTrue(user.is_student)

    def test_role_helper_properties(self):
        organizer = make_user("org", role=User.Role.ORGANIZER)
        admin_user = make_user("adm", role=User.Role.ADMIN)
        self.assertTrue(organizer.is_organizer)
        self.assertFalse(organizer.is_administrator)
        self.assertTrue(admin_user.is_administrator)

    def test_superuser_always_gets_admin_role(self):
        boss = User.objects.create_superuser("boss", "boss@example.com", "pass12345")
        self.assertEqual(boss.role, User.Role.ADMIN)

    def test_email_must_be_unique(self):
        make_user("first", email="same@example.com")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user("second", "same@example.com", "pass12345")

    def test_password_is_hashed(self):
        user = make_user("hashed")
        self.assertNotEqual(user.password, "pass12345")
        self.assertTrue(user.check_password("pass12345"))

    def test_display_name_falls_back_to_username(self):
        user = make_user("noname")
        self.assertEqual(user.display_name, "noname")
        user.first_name, user.last_name = "Ivan", "Makoha"
        self.assertEqual(user.display_name, "Ivan Makoha")
