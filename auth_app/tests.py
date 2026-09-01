"""Tests for the authentication endpoints."""
from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode

from .models import CustomUser
from .utils import encode_user_id, send_activation_email

LINK = "http://localhost:5500/activate.html?uid=Mw&token=abc"

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
        send_activation_email(user.pk, LINK)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn(LINK, message.body)
        self.assertNotIn("&amp;", message.body)
        html_body = message.alternatives[0][0]
        self.assertIn(LINK.replace("&", "&amp;"), html_body)
        self.assertEqual(message.to, ["user@example.com"])


class ActivationViewTests(TestCase):
    """Cover the GET /api/activate/<uidb64>/<token>/ endpoint."""

    def setUp(self):
        """Create an inactive account with a matching activation link."""
        self.user = CustomUser.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            is_active=False,
        )
        self.uidb64 = encode_user_id(self.user)
        self.token = default_token_generator.make_token(self.user)

    def activate(self, uidb64, token):
        """Call the activation endpoint with the given link parts."""
        return self.client.get(
            reverse("activate", kwargs={"uidb64": uidb64, "token": token})
        )

    def test_valid_link_activates_the_account(self):
        """A correct link answers with 200 and the documented message."""
        response = self.activate(self.uidb64, self.token)
        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["message"], "Account successfully activated."
        )
        self.assertTrue(self.user.is_active)

    def test_wrong_token_is_rejected(self):
        """A token that does not belong to the account fails with 400."""
        response = self.activate(self.uidb64, "invalid-token")
        self.user.refresh_from_db()
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.user.is_active)

    def test_broken_uid_is_rejected(self):
        """An id that is not decodable fails instead of raising an error."""
        response = self.activate("not-base64", self.token)
        self.assertEqual(response.status_code, 400)

    def test_unknown_user_is_rejected(self):
        """A well formed id of a missing account fails with 400."""
        response = self.activate(urlsafe_base64_encode(b"9999"), self.token)
        self.assertEqual(response.status_code, 400)

    def test_second_call_stays_successful(self):
        """Opening the link twice must not confuse the frontend."""
        self.activate(self.uidb64, self.token)
        response = self.activate(self.uidb64, self.token)
        self.assertEqual(response.status_code, 200)


class RegistrationToActivationTests(TestCase):
    """Cover the whole path from the registration to the active account."""

    @patch("auth_app.utils.django_rq.get_queue")
    def test_token_from_registration_activates_the_account(self, get_queue):
        """The token of the register response unlocks the new account."""
        response = self.client.post(reverse("register"), VALID_PAYLOAD)
        user = CustomUser.objects.get(pk=response.data["user"]["id"])
        self.assertFalse(user.is_active)
        link = self.activation_link(user, response.data["token"])
        self.assertEqual(self.client.get(link).status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    @staticmethod
    def activation_link(user, token):
        """Return the backend url that activates the given account."""
        kwargs = {"uidb64": encode_user_id(user), "token": token}
        return reverse("activate", kwargs=kwargs)
