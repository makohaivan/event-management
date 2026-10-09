from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.accounts.decorators import admin_required, organizer_required, student_required
from apps.accounts.models import User


@login_required
def dashboard_redirect(request):
    """Send each user to the dashboard that matches their role."""
    destinations = {
        User.Role.STUDENT: "dashboard:student",
        User.Role.ORGANIZER: "dashboard:organizer",
        User.Role.ADMIN: "dashboard:admin",
    }
    return redirect(destinations.get(request.user.role, "home"))


@student_required
def student_dashboard(request):
    return render(request, "dashboard/student.html")


@organizer_required
def organizer_dashboard(request):
    return render(request, "dashboard/organizer.html")


@admin_required
def admin_dashboard(request):
    return render(request, "dashboard/admin.html")
