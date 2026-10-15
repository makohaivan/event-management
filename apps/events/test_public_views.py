from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.events.models import Event
from apps.events.queries import public_events
from apps.factories import (
    make_category, make_event, make_organizer, make_registration, make_user,
)

S = Event.Status


def titles(page_or_queryset):
    return [event.title for event in page_or_queryset]


class VisibilityTests(TestCase):
    def test_only_approved_upcoming_events_are_public(self):
        make_event(title="Live", status=S.APPROVED, days_ahead=3)
        make_event(title="Today", status=S.APPROVED, days_ahead=0)
        make_event(title="Draft", status=S.DRAFT)
        make_event(title="Pending", status=S.PENDING)
        make_event(title="Rejected", status=S.REJECTED)
        make_event(title="Cancelled", status=S.CANCELLED)
        make_event(title="Past", status=S.APPROVED, days_ahead=-2)
        self.assertEqual(set(titles(public_events())), {"Live", "Today"})


class HomePageTests(TestCase):
    def test_anonymous_visitors_can_open_the_home_page(self):
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)

    def test_empty_state_message(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "No upcoming events yet")

    def test_featured_section_only_lists_featured_events(self):
        make_event(title="Star", is_featured=True)
        make_event(title="Ordinary", is_featured=False)
        response = self.client.get(reverse("home"))
        self.assertEqual(titles(response.context["featured_events"]), ["Star"])

    def test_upcoming_events_are_soonest_first(self):
        make_event(title="Later", days_ahead=9)
        make_event(title="Sooner", days_ahead=2)
        response = self.client.get(reverse("home"))
        self.assertEqual(titles(response.context["upcoming_events"]), ["Sooner", "Later"])

    def test_recently_added_shows_newest_first(self):
        make_event(title="First added")
        make_event(title="Second added")
        response = self.client.get(reverse("home"))
        self.assertEqual(titles(response.context["recent_events"]), ["Second added", "First added"])

    def test_hidden_events_do_not_appear(self):
        make_event(title="Secret draft", status=S.DRAFT)
        make_event(title="Old news", days_ahead=-3)
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "Secret draft")
        self.assertNotContains(response, "Old news")

    def test_category_counts_only_include_public_events(self):
        tech = make_category("Technology")
        make_event(title="A", category=tech)
        make_event(title="B", category=tech)
        make_event(title="C", category=tech, status=S.DRAFT)
        response = self.client.get(reverse("home"))
        counts = {c.name: c.upcoming_total for c in response.context["categories"]}
        self.assertEqual(counts["Technology"], 2)

    def test_home_search_box_points_to_event_list(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, reverse("events:list"))


class EventListTests(TestCase):
    def setUp(self):
        self.tech = make_category("Technology")
        self.sports = make_category("Sports")
        self.hack = make_event(title="Hack Night", category=self.tech, venue="Lab", days_ahead=3)
        self.final = make_event(title="Football Final", category=self.sports, venue="Stadium", days_ahead=10)
        self.workshop = make_event(title="Django Workshop", category=self.tech, venue="Lab", days_ahead=20)
        self.url = reverse("events:list")

    def listed(self, **params):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200)
        return titles(response.context["page_obj"]), response

    def test_anonymous_visitors_can_browse(self):
        names, _ = self.listed()
        self.assertEqual(names, ["Hack Night", "Football Final", "Django Workshop"])

    def test_hidden_events_are_not_listed(self):
        make_event(title="Draft thing", status=S.DRAFT)
        make_event(title="Last week", days_ahead=-7)
        names, _ = self.listed()
        self.assertNotIn("Draft thing", names)
        self.assertNotIn("Last week", names)

    def test_search_by_name_ignores_case(self):
        names, _ = self.listed(q="HACK")
        self.assertEqual(names, ["Hack Night"])

    def test_search_with_no_results_shows_friendly_message(self):
        names, response = self.listed(q="zzz")
        self.assertEqual(names, [])
        self.assertContains(response, "No events match your search")

    def test_filter_by_category(self):
        names, _ = self.listed(category=self.sports.slug)
        self.assertEqual(names, ["Football Final"])

    def test_filter_by_venue(self):
        names, _ = self.listed(venue="lab")
        self.assertEqual(names, ["Hack Night", "Django Workshop"])

    def test_filter_by_date_range(self):
        today = timezone.localdate()
        names, _ = self.listed(
            date_from=(today + timedelta(days=5)).isoformat(),
            date_to=(today + timedelta(days=15)).isoformat(),
        )
        self.assertEqual(names, ["Football Final"])

    def test_combined_filters(self):
        names, _ = self.listed(q="night", category=self.tech.slug, venue="Lab")
        self.assertEqual(names, ["Hack Night"])

    def test_sorting(self):
        self.assertEqual(self.listed(sort="latest")[0],
                         ["Django Workshop", "Football Final", "Hack Night"])
        self.assertEqual(self.listed(sort="newest")[0],
                         ["Django Workshop", "Football Final", "Hack Night"])
        self.assertEqual(self.listed(sort="title")[0],
                         ["Django Workshop", "Football Final", "Hack Night"])
        self.assertEqual(self.listed(sort="soonest")[0],
                         ["Hack Night", "Football Final", "Django Workshop"])

    def test_invalid_filter_values_are_ignored(self):
        names, _ = self.listed(date_from="not-a-date", date_to="31/12/2026", sort="zzz")
        self.assertEqual(len(names), 3)

    def test_unknown_category_slug_shows_nothing(self):
        names, response = self.listed(category="no-such-category")
        self.assertEqual(names, [])
        self.assertContains(response, "No events match your search")

    def test_filters_are_shown_back_in_the_form(self):
        _, response = self.listed(q="hack")
        self.assertContains(response, 'value="hack"')
        self.assertTrue(response.context["has_filters"])

    def test_pagination_keeps_the_filters(self):
        for number in range(11):
            make_event(title=f"Tech extra {number:02d}", category=self.tech)
        response = self.client.get(self.url, {"category": self.tech.slug})
        self.assertEqual(len(response.context["page_obj"]), 9)
        self.assertContains(response, f"category={self.tech.slug}&page=2")
        second = self.client.get(self.url, {"category": self.tech.slug, "page": 2})
        self.assertEqual(len(second.context["page_obj"]), 4)

    def test_full_event_card_says_registration_full(self):
        full = make_event(title="Tiny event", capacity=1)
        make_registration(make_user("s1"), full)
        _, response = self.listed(q="tiny")
        self.assertContains(response, "Registration Full")

    def test_event_card_shows_seats_left(self):
        event = make_event(title="Roomy", capacity=10)
        make_registration(make_user("s1"), event)
        _, response = self.listed(q="roomy")
        self.assertContains(response, "9 seats left")


class EventDetailTests(TestCase):
    def setUp(self):
        self.organizer = make_organizer("organizer1")

    def open(self, event, user=None):
        if user:
            self.client.login(username=user.username, password="pass12345")
        return self.client.get(reverse("events:detail", args=[event.slug]))

    def test_anonymous_visitors_can_view_an_approved_event(self):
        event = make_event(title="Open day", venue="Great Hall")
        response = self.open(event)
        self.assertContains(response, "Open day")
        self.assertContains(response, "Great Hall")
        self.assertContains(response, "Registration is open until")

    def test_capacity_registered_and_available_are_shown(self):
        event = make_event(capacity=100)
        make_registration(make_user("s1"), event)
        make_registration(make_user("s2"), event)
        response = self.open(event)
        self.assertEqual(response.context["event"].registered_total, 2)
        self.assertEqual(response.context["event"].seats_left, 98)
        self.assertContains(response, "Capacity")
        self.assertContains(response, "Available")

    def test_cancelled_registration_does_not_use_a_seat(self):
        event = make_event(capacity=5)
        registration = make_registration(make_user("s1"), event)
        registration.cancel()
        self.assertEqual(self.open(event).context["event"].seats_left, 5)

    def test_full_event_says_registration_full(self):
        event = make_event(capacity=1)
        make_registration(make_user("s1"), event)
        response = self.open(event)
        self.assertEqual(response.context["registration_state"], "full")
        self.assertContains(response, "Registration Full")

    def test_passed_deadline_message(self):
        event = make_event(registration_deadline=timezone.now() - timedelta(hours=1))
        response = self.open(event)
        self.assertEqual(response.context["registration_state"], "closed")
        self.assertContains(response, "Registration deadline has passed.")

    def test_cancelled_event_is_visible_but_closed(self):
        event = make_event(status=S.CANCELLED)
        response = self.open(event)
        self.assertContains(response, "This event has been cancelled.")
        self.assertEqual(response.context["registration_state"], "unavailable")

    def test_completed_past_event_is_visible_but_closed(self):
        event = make_event(status=S.COMPLETED, days_ahead=-3)
        response = self.open(event)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["registration_state"], "unavailable")

    def test_unpublished_events_return_404_for_the_public(self):
        make_user("stu")
        for status in (S.DRAFT, S.PENDING, S.REJECTED):
            event = make_event(status=status, organizer=self.organizer)
            self.assertEqual(self.open(event).status_code, 404)
            self.assertEqual(self.open(event, make_user("stu")).status_code, 404)
            self.client.logout()

    def test_owner_and_admin_can_preview_unpublished_events(self):
        event = make_event(status=S.PENDING, organizer=self.organizer)
        response = self.open(event, self.organizer)
        self.assertContains(response, "Preview")
        self.client.logout()
        admin_user = make_user("adm", role=User.Role.ADMIN)
        self.assertEqual(self.open(event, admin_user).status_code, 200)

    def test_other_organizers_cannot_preview(self):
        event = make_event(status=S.DRAFT, organizer=self.organizer)
        other = make_organizer("organizer2")
        self.assertEqual(self.open(event, other).status_code, 404)

    def test_unknown_event_returns_404(self):
        self.assertEqual(self.client.get(reverse("events:detail", args=["no-such-event"])).status_code, 404)

    def test_related_events_share_the_category(self):
        tech = make_category("Technology")
        sports = make_category("Sports")
        main = make_event(title="Main", category=tech)
        make_event(title="Same category", category=tech)
        make_event(title="Other category", category=sports)
        make_event(title="Hidden same category", category=tech, status=S.DRAFT)
        response = self.open(main)
        self.assertEqual(titles(response.context["related_events"]), ["Same category"])

    def test_anonymous_visitor_sees_login_link_with_next(self):
        event = make_event()
        response = self.open(event)
        self.assertContains(response, "Log in to register")
        self.assertContains(response, "next=")

    def test_logged_in_student_does_not_see_login_prompt(self):
        event = make_event()
        response = self.open(event, make_user("stu"))
        self.assertNotContains(response, "Log in to register")


class NavigationAndDemoDataTests(TestCase):
    def test_browse_events_link_is_visible_to_everyone(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Browse Events")

    def test_demo_command_creates_public_events_once(self):
        call_command("seed_demo_events", verbosity=0)
        first_count = Event.objects.count()
        call_command("seed_demo_events", verbosity=0)
        self.assertEqual(Event.objects.count(), first_count)
        self.assertGreaterEqual(first_count, 10)
        self.assertEqual(public_events().count(), first_count)
        self.assertTrue(Event.objects.filter(is_featured=True).exists())
        organizer = User.objects.get(username="demo_organizer")
        self.assertTrue(organizer.is_organizer)
        self.assertTrue(organizer.check_password("demo12345"))
