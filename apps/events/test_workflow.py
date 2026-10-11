from django.test import TestCase

from apps.events.models import Event
from apps.factories import make_event

S = Event.Status


class EventWorkflowTests(TestCase):
    def test_submit_moves_draft_to_pending(self):
        event = make_event(status=S.DRAFT)
        event.submit_for_approval()
        event.refresh_from_db()
        self.assertEqual(event.status, S.PENDING)

    def test_approve_moves_pending_to_approved(self):
        event = make_event(status=S.PENDING)
        event.approve()
        self.assertEqual(event.status, S.APPROVED)

    def test_reject_stores_reason_and_resubmit_clears_it(self):
        event = make_event(status=S.PENDING)
        event.reject("Add a venue address.")
        self.assertEqual(event.status, S.REJECTED)
        self.assertEqual(event.rejection_reason, "Add a venue address.")
        event.submit_for_approval()
        event.refresh_from_db()
        self.assertEqual(event.status, S.PENDING)
        self.assertEqual(event.rejection_reason, "")

    def test_cancel_only_from_approved(self):
        make_event(status=S.APPROVED).cancel()
        with self.assertRaises(ValueError):
            make_event(status=S.DRAFT).cancel()

    def test_complete_requires_started_event(self):
        past = make_event(status=S.APPROVED, days_ahead=-1)
        past.mark_completed()
        self.assertEqual(past.status, S.COMPLETED)
        with self.assertRaises(ValueError):
            make_event(status=S.APPROVED, days_ahead=5).mark_completed()

    def test_invalid_transitions_raise(self):
        with self.assertRaises(ValueError):
            make_event(status=S.DRAFT).approve()
        with self.assertRaises(ValueError):
            make_event(status=S.APPROVED).submit_for_approval()
        with self.assertRaises(ValueError):
            make_event(status=S.CANCELLED).reject("no")

    def test_permission_flags(self):
        self.assertTrue(make_event(status=S.DRAFT).organizer_can_edit)
        self.assertTrue(make_event(status=S.APPROVED).organizer_can_edit)
        self.assertFalse(make_event(status=S.PENDING).organizer_can_edit)
        self.assertFalse(make_event(status=S.COMPLETED).organizer_can_edit)
        self.assertTrue(make_event(status=S.REJECTED).organizer_can_delete)
        self.assertFalse(make_event(status=S.APPROVED).organizer_can_delete)
