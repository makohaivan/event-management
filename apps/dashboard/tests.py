from django.test import TestCase
from django.urls import reverse


class HomePageTest(TestCase):
    def test_home_page_loads(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)

    def test_home_page_uses_base_template(self):
        response = self.client.get(reverse("home"))
        self.assertTemplateUsed(response, "base.html")
