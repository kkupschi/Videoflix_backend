"""URL routes for the authentication endpoints."""
from django.urls import path

from .views import ActivationView, RegistrationView

urlpatterns = [
    path("register/", RegistrationView.as_view(), name="register"),
    path(
        "activate/<str:uidb64>/<str:token>/",
        ActivationView.as_view(),
        name="activate",
    ),
]
