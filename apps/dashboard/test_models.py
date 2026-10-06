from django.test import TestCase

from apps.dashboard.models import ProblemReport
from apps.factories import make_user


class ProblemReportTests(TestCase):
    def test_new_report_is_open(self):
        report = ProblemReport.objects.create(
            reported_by=make_user(), subject="Cannot register", description="Page errors out."
        )
        self.assertEqual(report.status, ProblemReport.Status.OPEN)
        self.assertEqual(str(report), "Cannot register")
