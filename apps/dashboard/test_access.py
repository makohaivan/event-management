from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.factories import make_user

DENIED_MESSAGE = "You do not have permission to perform this action."


class DashboardAccessTests(TestCase):
    def setUp(self):
        self.student = make_user("stu")
        self.organizer = make_user("org", role=User.Role.ORGANIZER)
        self.admin_user = make_user("adm", role=User.Role.ADMIN)

    def open_as(self, username, url_name):
        self.client.logout()
        self.client.login(username=username, password="pass12345")
        return self.client.get(reverse(url_name))

    def test_anonymous_users_are_sent_to_login(self):
        for url_name in ("dashboard:student", "dashboard:organizer", "dashboard:admin",
                         "dashboard:redirect"):
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_each_role_can_open_its_own_dashboard(self):
        self.assertEqual(self.open_as("stu", "dashboard:student").status_code, 200)
        self.assertEqual(self.open_as("org", "dashboard:organizer").status_code, 200)
        self.assertEqual(self.open_as("adm", "dashboard:admin").status_code, 200)

    def test_student_cannot_open_organizer_or_admin_pages(self):
        self.assertEqual(self.open_as("stu", "dashboard:organizer").status_code, 403)
        self.assertEqual(self.open_as("stu", "dashboard:admin").status_code, 403)

    def test_organizer_cannot_open_student_or_admin_pages(self):
        self.assertEqual(self.open_as("org", "dashboard:student").status_code, 403)
        self.assertEqual(self.open_as("org", "dashboard:admin").status_code, 403)

    def test_administrator_cannot_open_student_or_organizer_pages(self):
        self.assertEqual(self.open_as("adm", "dashboard:student").status_code, 403)
        self.assertEqual(self.open_as("adm", "dashboard:organizer").status_code, 403)

    def test_forbidden_page_shows_friendly_message(self):
        response = self.open_as("stu", "dashboard:admin")
        self.assertContains(response, DENIED_MESSAGE, status_code=403)

    def test_missing_page_shows_friendly_404(self):
        response = self.client.get("/this-page-does-not-exist/")
        self.assertContains(response, "could not find the page", status_code=404)

    def test_dashboard_redirect_routes_by_role(self):
        for username, target in (("stu", "dashboard:student"),
                                 ("org", "dashboard:organizer"),
                                 ("adm", "dashboard:admin")):
            response = self.open_as(username, "dashboard:redirect")
            self.assertRedirects(response, reverse(target))
