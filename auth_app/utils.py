"""Helper functions for the authentication endpoints."""
import django_rq
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework_simplejwt.tokens import RefreshToken

from .models import CustomUser

ACTIVATION_SUBJECT = "Confirm your email"
ACTIVATION_SUCCESS = "Account successfully activated."
ACTIVATION_FAILED = "Activation failed."
LOGIN_SUCCESS = "Login successful"


def encode_user_id(user):
    """Return the primary key of the user as base64 encoded string."""
    return urlsafe_base64_encode(force_bytes(user.pk))


def build_activation_url(user, token):
    """Return the frontend link that starts the account activation."""
    return settings.ACTIVATION_URL_TEMPLATE.format(
        uid=encode_user_id(user), token=token
    )


def build_email_message(subject, recipient, template, context):
    """Return a mail with a plain text body and an html alternative."""
    text_body = render_to_string(f"emails/{template}.txt", context)
    html_body = render_to_string(f"emails/{template}.html", context)
    message = EmailMultiAlternatives(
        subject, text_body, settings.DEFAULT_FROM_EMAIL, [recipient]
    )
    message.attach_alternative(html_body, "text/html")
    return message


def send_activation_email(user_id, activation_url):
    """Send the activation mail. This runs inside the RQ worker."""
    user = CustomUser.objects.get(pk=user_id)
    context = {"user": user, "activation_url": activation_url}
    message = build_email_message(
        ACTIVATION_SUBJECT, user.email, "activation", context
    )
    message.send()


def queue_activation_email(user, token):
    """Hand the activation mail over to the background worker."""
    queue = django_rq.get_queue("default")
    activation_url = build_activation_url(user, token)
    queue.enqueue(send_activation_email, user.pk, activation_url)


def build_registration_response(user, token):
    """Return the response body that the api documentation defines."""
    return {"user": {"id": user.id, "email": user.email}, "token": token}


def get_user_by_uidb64(uidb64):
    """Return the account behind the encoded id or None if it does not fit."""
    try:
        user_id = urlsafe_base64_decode(uidb64).decode()
        return CustomUser.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        return None


def activate_user(user):
    """Switch the account to active and leave every other field alone."""
    if user.is_active:
        return
    user.is_active = True
    user.save(update_fields=["is_active"])


def create_activation_token(user):
    """Return a signed token that is bound to the given account."""
    return default_token_generator.make_token(user)


def is_activation_valid(user, token):
    """Return True when the token belongs to the given account."""
    if user is None:
        return False
    return default_token_generator.check_token(user, token)


def authenticate_by_email(email, password):
    """Return the matching active account or None for any other case."""
    user = CustomUser.objects.filter(email__iexact=email).first()
    if user is None:
        return None
    return authenticate(username=user.username, password=password)


def create_token_pair(user):
    """Return a fresh refresh token and access token for the account."""
    refresh = RefreshToken.for_user(user)
    return str(refresh), str(refresh.access_token)


def build_login_response(user):
    """Return the response body that the api documentation defines."""
    account = {"id": user.id, "username": user.username}
    return {"detail": LOGIN_SUCCESS, "user": account}


def set_token_cookie(response, name, value, lifetime):
    """Store one token in a cookie that scripts cannot read."""
    response.set_cookie(
        key=name,
        value=value,
        max_age=int(lifetime.total_seconds()),
        httponly=True,
        secure=settings.JWT_COOKIE_SECURE,
        samesite=settings.JWT_COOKIE_SAMESITE,
        path="/",
    )


def set_auth_cookies(response, access, refresh):
    """Attach both token cookies to the given response."""
    lifetimes = settings.SIMPLE_JWT
    access_name = settings.JWT_ACCESS_COOKIE
    refresh_name = settings.JWT_REFRESH_COOKIE
    set_token_cookie(response, access_name, access,
                     lifetimes["ACCESS_TOKEN_LIFETIME"])
    set_token_cookie(response, refresh_name, refresh,
                     lifetimes["REFRESH_TOKEN_LIFETIME"])
    return response
