from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    # Organizer
    path("manage/", views.my_events, name="my_events"),
    path("manage/create/", views.event_create, name="create"),
    path("manage/<int:pk>/", views.event_manage_detail, name="manage_detail"),
    path("manage/<int:pk>/edit/", views.event_edit, name="edit"),
    path("manage/<int:pk>/delete/", views.event_delete, name="delete"),
    path("manage/<int:pk>/submit/", views.event_submit, name="submit"),
    path("manage/<int:pk>/cancel/", views.event_cancel, name="cancel"),
    path("manage/<int:pk>/complete/", views.event_complete, name="complete"),
    # Administrator: events
    path("admin/", views.admin_event_list, name="admin_list"),
    path("admin/create/", views.admin_event_create, name="admin_create"),
    path("admin/<int:pk>/edit/", views.admin_event_edit, name="admin_edit"),
    path("admin/<int:pk>/delete/", views.admin_event_delete, name="admin_delete"),
    path("admin/<int:pk>/cancel/", views.admin_event_cancel, name="admin_cancel"),
    # Administrator: approvals
    path("admin/approvals/", views.event_approvals, name="approvals"),
    path("admin/<int:pk>/approve/", views.event_approve, name="approve"),
    path("admin/<int:pk>/reject/", views.event_reject, name="reject"),
    # Administrator: categories
    path("admin/categories/", views.category_list, name="category_list"),
    path("admin/categories/create/", views.category_create, name="category_create"),
    path("admin/categories/<int:pk>/edit/", views.category_edit, name="category_edit"),
    path("admin/categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
]
