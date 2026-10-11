from django.test import TestCase
from django.urls import reverse

from apps.factories import make_organizer, make_user


class RoleNavigationTests(TestCase):
    def test_organizer_sees_event_links_only(self):
        make_organizer("org")
        self.client.login(username="org", password="pass12345")
        response = self.client.get(reverse("home"))
        self.assertContains(response, "My Events")
        self.assertNotContains(response, "Approvals")

    def test_administrator_sees_management_links(self):
        make_user("adm", role="admin")
        self.client.login(username="adm", password="pass12345")
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Approvals")
        self.assertContains(response, "Categories")
        self.assertNotContains(response, "My Events")

    def test_student_sees_no_management_links(self):
        make_user("stu")
        self.client.login(username="stu", password="pass12345")
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "Approvals")
        self.assertNotContains(response, "My Events")
