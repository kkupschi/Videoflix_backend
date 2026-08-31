"""Tests for the authentication endpoints."""
from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .models import CustomUser
from .utils import send_activation_email

VALID_PAYLOAD = {
    "email": "user@example.com",
    "password": "securepassword123",
    "confirmed_password": "securepassword123",
}


class RegistrationViewTests(TestCase):
    """Cover the POST /api/register/ endpoint."""

    def setUp(self):
        """Provide the endpoint url and silence the background queue."""
        self.url = reverse("register")
        patcher = patch("auth_app.utils.django_rq.get_queue")
        self.queue = patcher.start().return_value
        self.addCleanup(patcher.stop)

    def test_registration_returns_created_payload(self):
        """A valid payload answers with 201 and the documented body."""
        response = self.client.post(self.url, VALID_PAYLOAD)
        user = CustomUser.objects.get(email="user@example.com")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["user"]["id"], user.id)
        self.assertEqual(response.data["user"]["email"], user.email)
        self.assertTrue(response.data["token"])

    def test_new_account_stays_inactive(self):
        """The account must not be usable before the activation."""
        self.client.post(self.url, VALID_PAYLOAD)
        user = CustomUser.objects.get(email="user@example.com")
        self.assertFalse(user.is_active)
        self.assertEqual(user.username, "user@example.com")

    def test_activation_mail_is_queued(self):
        """Sending the mail is handed over to the background worker."""
        self.client.post(self.url, VALID_PAYLOAD)
        self.assertEqual(self.queue.enqueue.call_count, 1)

    def test_known_email_is_rejected_generically(self):
        """A taken address must not be revealed to the caller."""
        CustomUser.objects.create_user(username="a", email="user@example.com")
        response = self.client.post(self.url, VALID_PAYLOAD)
        self.assertEqual(response.status_code, 400)
        self.assertIn("check your entries", str(response.data["email"][0]))

    def test_password_mismatch_is_rejected(self):
        """Two different passwords must not create an account."""
        payload = dict(VALID_PAYLOAD, confirmed_password="somethingelse")
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(CustomUser.objects.count(), 0)

    def test_weak_password_is_rejected(self):
        """The Django password policy is applied on registration."""
        payload = dict(VALID_PAYLOAD, password="123", confirmed_password="123")
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(CustomUser.objects.count(), 0)


class ActivationMailTests(TestCase):
    """Cover the rendering and the delivery of the activation mail."""

    def test_mail_contains_activation_link(self):
        """Both mail bodies carry the link the frontend has to open."""
        user = CustomUser.objects.create_user(
            username="user@example.com", email="user@example.com"
        )
        send_activation_email(user.pk, "http://localhost:5500/activate")
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn("http://localhost:5500/activate", message.body)
        self.assertIn("http://localhost:5500/activate", message.alternatives[0][0])
        self.assertEqual(message.to, ["user@example.com"])
