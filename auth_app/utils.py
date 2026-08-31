"""Helper functions for the authentication endpoints."""
import django_rq
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import CustomUser

ACTIVATION_SUBJECT = "Confirm your email"


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
