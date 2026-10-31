from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from apps.events import public_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("events/", include("apps.events.urls")),
    path("", include("apps.registrations.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("", public_views.home, name="home"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
