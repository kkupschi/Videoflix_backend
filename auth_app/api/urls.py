"""URL routes for the authentication endpoints."""
from django.urls import path

from .views import (
    ActivationView,
    LoginView,
    LogoutView,
    RegistrationView,
    TokenRefreshView,
)

urlpatterns = [
    path("register/", RegistrationView.as_view(), name="register"),
    path(
        "activate/<str:uidb64>/<str:token>/",
        ActivationView.as_view(),
        name="activate",
    ),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path(
        "token/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),
]
