from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_redirect, name="redirect"),
    path("student/", views.student_dashboard, name="student"),
    path("organizer/", views.organizer_dashboard, name="organizer"),
    path("admin/", views.admin_dashboard, name="admin"),
]
