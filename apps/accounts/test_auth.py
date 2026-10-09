from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.factories import make_user

VALID_SIGNUP = {
    "username": "ivan",
    "first_name": "Ivan",
    "last_name": "Makoha",
    "email": "ivan@example.com",
    "student_number": "2023/001",
    "faculty": "Computing",
    "phone": "0700000000",
    "password1": "Str0ng-Pass-123",
    "password2": "Str0ng-Pass-123",
}


class RegistrationTests(TestCase):
    def test_register_page_loads(self):
        response = self.client.get(reverse("accounts:register"))
        self.assertEqual(response.status_code, 200)

    def test_student_can_register_and_is_logged_in(self):
        response = self.client.post(reverse("accounts:register"), VALID_SIGNUP)
        self.assertRedirects(response, reverse("dashboard:redirect"), fetch_redirect_response=False)
        user = User.objects.get(username="ivan")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_role_cannot_be_chosen_at_signup(self):
        self.client.post(reverse("accounts:register"), {**VALID_SIGNUP, "role": "admin"})
        self.assertEqual(User.objects.get(username="ivan").role, User.Role.STUDENT)

    def test_duplicate_email_is_rejected_ignoring_case(self):
        make_user("existing", email="ivan@example.com")
        response = self.client.post(
            reverse("accounts:register"), {**VALID_SIGNUP, "email": "IVAN@example.com"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertEqual(User.objects.count(), 1)

    def test_password_mismatch_is_rejected(self):
        response = self.client.post(
            reverse("accounts:register"), {**VALID_SIGNUP, "password2": "different-Pass-999"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="ivan").exists())

    def test_weak_password_is_rejected(self):
        response = self.client.post(
            reverse("accounts:register"),
            {**VALID_SIGNUP, "password1": "12345678", "password2": "12345678"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="ivan").exists())

    def test_required_fields_are_enforced(self):
        response = self.client.post(
            reverse("accounts:register"), {**VALID_SIGNUP, "first_name": "", "email": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("first_name", response.context["form"].errors)
        self.assertIn("email", response.context["form"].errors)

    def test_logged_in_user_is_redirected_away_from_register(self):
        make_user("stu")
        self.client.login(username="stu", password="pass12345")
        response = self.client.get(reverse("accounts:register"))
        self.assertEqual(response.status_code, 302)


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.student = make_user("stu")
        self.organizer = make_user("org", role=User.Role.ORGANIZER)
        self.admin_user = make_user("adm", role=User.Role.ADMIN)

    def log_in(self, username, **extra):
        return self.client.post(
            reverse("accounts:login"), {"username": username, "password": "pass12345"}, **extra
        )

    def test_each_role_lands_on_its_own_dashboard(self):
        expected = {
            "stu": reverse("dashboard:student"),
            "org": reverse("dashboard:organizer"),
            "adm": reverse("dashboard:admin"),
        }
        for username, dashboard_url in expected.items():
            self.client.logout()
            response = self.log_in(username, follow=True)
            self.assertEqual(response.redirect_chain[-1][0], dashboard_url)
            self.assertEqual(response.status_code, 200)

    def test_invalid_login_shows_friendly_error(self):
        response = self.client.post(
            reverse("accounts:login"), {"username": "stu", "password": "wrong-pass"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password. Please try again.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_ends_the_session(self):
        self.log_in("stu")
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logged_in_user_skips_the_login_page(self):
        self.log_in("stu")
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 302)

    def test_inactive_user_cannot_log_in(self):
        self.student.is_active = False
        self.student.save()
        self.log_in("stu")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_navbar_changes_with_login_state(self):
        anonymous = self.client.get(reverse("home"))
        self.assertContains(anonymous, "Register")
        self.log_in("stu")
        logged_in = self.client.get(reverse("home"))
        self.assertContains(logged_in, "Log out")


class ProfileTests(TestCase):
    def setUp(self):
        self.student = make_user("stu")
        self.client.login(username="stu", password="pass12345")

    def profile_data(self, **overrides):
        data = {
            "first_name": "Ivan",
            "last_name": "Makoha",
            "email": "stu@example.com",
            "phone": "0711111111",
            "student_number": "2023/777",
            "faculty": "Computing",
        }
        data.update(overrides)
        return data

    def test_profile_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("accounts:profile"))
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('accounts:profile')}",
            fetch_redirect_response=False,
        )

    def test_user_can_update_own_profile(self):
        response = self.client.post(reverse("accounts:profile"), self.profile_data())
        self.assertRedirects(response, reverse("accounts:profile"))
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, "Ivan")
        self.assertEqual(self.student.faculty, "Computing")

    def test_role_cannot_be_changed_through_profile(self):
        self.client.post(reverse("accounts:profile"), self.profile_data(role="admin"))
        self.student.refresh_from_db()
        self.assertEqual(self.student.role, User.Role.STUDENT)

    def test_cannot_take_another_users_email(self):
        make_user("other", email="taken@example.com")
        response = self.client.post(
            reverse("accounts:profile"), self.profile_data(email="TAKEN@example.com")
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)

    def test_user_can_change_password(self):
        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": "pass12345",
                "new_password1": "Another-Str0ng-1",
                "new_password2": "Another-Str0ng-1",
            },
        )
        self.assertRedirects(response, reverse("accounts:profile"), fetch_redirect_response=False)
        self.student.refresh_from_db()
        self.assertTrue(self.student.check_password("Another-Str0ng-1"))

    def test_wrong_old_password_is_rejected(self):
        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": "not-my-password",
                "new_password1": "Another-Str0ng-1",
                "new_password2": "Another-Str0ng-1",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertTrue(self.student.check_password("pass12345"))
