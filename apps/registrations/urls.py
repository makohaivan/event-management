from django.urls import path

from . import views

app_name = "registrations"

urlpatterns = [
    path("events/<slug:slug>/register/", views.register, name="register"),
    path("registrations/", views.my_registrations, name="my_registrations"),
    path("registrations/<str:number>/", views.registration_detail, name="detail"),
    path("registrations/<str:number>/qr.png", views.qr_image, name="qr"),
    path("registrations/<str:number>/cancel/", views.cancel, name="cancel"),
]
