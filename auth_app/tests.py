"""Tests for the authentication endpoints."""
from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIRequestFactory
from rest_framework_simplejwt.exceptions import InvalidToken

from .api.authentication import CookieJWTAuthentication
from .models import CustomUser
from .utils import create_token_pair, encode_user_id, send_activation_email

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

    def test_failure_keeps_the_message_key(self):
        """Success and failure use the same key, as the endpoint docs do."""
        response = self.activate(self.uidb64, "invalid-token")
        self.assertIn("message", response.data)
        self.assertNotIn("detail", response.data)

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


class LoginViewTests(TestCase):
    """Cover the POST /api/login/ endpoint."""

    def setUp(self):
        """Provide the endpoint url and one active account."""
        self.url = reverse("login")
        self.user = CustomUser.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password="securepassword123",
        )

    def login(self, email="user@example.com", password="securepassword123"):
        """Send a login request with the given credentials."""
        return self.client.post(
            self.url, {"email": email, "password": password}
        )

    def test_valid_login_returns_documented_body(self):
        """A correct login answers with 200 and the documented body."""
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["detail"], "Login successful")
        self.assertEqual(response.data["user"]["id"], self.user.id)
        self.assertEqual(response.data["user"]["username"], self.user.username)

    def test_valid_login_sets_both_cookies(self):
        """Both tokens land in cookies that scripts cannot read."""
        response = self.login()
        for name in ("access_token", "refresh_token"):
            cookie = response.cookies[name]
            self.assertTrue(cookie.value)
            self.assertTrue(cookie["httponly"])
            self.assertEqual(cookie["samesite"], "Lax")

    def test_no_token_appears_in_the_body(self):
        """The tokens must travel in cookies only, never in the body."""
        body = str(self.login().data)
        self.assertNotIn("access", body)
        self.assertNotIn("refresh", body)

    def test_wrong_password_is_rejected_generically(self):
        """A wrong password answers with 401 and no detail about it."""
        response = self.login(password="wrongpassword")
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("access_token", response.cookies)

    def test_unknown_email_is_rejected_generically(self):
        """An unknown address gives the same answer as a wrong password."""
        wrong_password = self.login(password="wrongpassword")
        unknown = self.login(email="nobody@example.com")
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(str(unknown.data), str(wrong_password.data))

    def test_inactive_account_cannot_log_in(self):
        """An account without activation must not receive tokens."""
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        response = self.login()
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("access_token", response.cookies)


class CookieAuthenticationTests(TestCase):
    """Cover the authentication that reads the token from the cookie."""

    def setUp(self):
        """Provide an account, a request factory and the class under test."""
        self.user = CustomUser.objects.create_user(
            username="user@example.com", email="user@example.com"
        )
        self.factory = APIRequestFactory()
        self.backend = CookieJWTAuthentication()

    def request_with_cookie(self, value=None):
        """Build a request that optionally carries an access cookie."""
        request = self.factory.get("/")
        if value is not None:
            request.COOKIES["access_token"] = value
        return request

    def test_valid_cookie_identifies_the_account(self):
        """A valid token in the cookie resolves to the right account."""
        _, access = create_token_pair(self.user)
        user, _ = self.backend.authenticate(self.request_with_cookie(access))
        self.assertEqual(user, self.user)

    def test_missing_cookie_stays_anonymous(self):
        """Without a cookie the request is simply not authenticated."""
        request = self.request_with_cookie()
        self.assertIsNone(self.backend.authenticate(request))

    def test_broken_token_is_rejected(self):
        """A manipulated token must not pass as a valid account."""
        with self.assertRaises(InvalidToken):
            self.backend.authenticate(self.request_with_cookie("kaputt"))

    def test_header_alone_is_not_enough(self):
        """A token in the Authorization header is ignored on purpose."""
        _, access = create_token_pair(self.user)
        request = self.factory.get("/", HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertIsNone(self.backend.authenticate(request))


class TokenRefreshViewTests(TestCase):
    """Cover the POST /api/token/refresh/ endpoint."""

    def setUp(self):
        """Provide the endpoint url and an account with a token pair."""
        self.url = reverse("token_refresh")
        self.user = CustomUser.objects.create_user(
            username="user@example.com", email="user@example.com"
        )
        self.refresh, self.access = create_token_pair(self.user)

    def refresh_with(self, cookie=None):
        """Post to the endpoint, optionally carrying a refresh cookie."""
        if cookie is not None:
            self.client.cookies["refresh_token"] = cookie
        return self.client.post(self.url)

    def test_valid_cookie_returns_documented_body(self):
        """A valid refresh cookie answers with the documented body."""
        response = self.refresh_with(self.refresh)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["detail"], "Token refreshed")
        self.assertTrue(response.data["access"])

    def test_valid_cookie_sets_a_new_access_cookie(self):
        """The renewed access token lands in an HttpOnly cookie."""
        response = self.refresh_with(self.refresh)
        cookie = response.cookies["access_token"]
        self.assertEqual(cookie.value, response.data["access"])
        self.assertTrue(cookie["httponly"])

    def test_renewed_token_authenticates(self):
        """The renewed token really identifies the same account."""
        response = self.refresh_with(self.refresh)
        request = APIRequestFactory().get("/")
        request.COOKIES["access_token"] = response.data["access"]
        user, _ = CookieJWTAuthentication().authenticate(request)
        self.assertEqual(user, self.user)

    def test_missing_cookie_answers_with_400(self):
        """Without a refresh cookie the request is incomplete."""
        response = self.refresh_with()
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access_token", response.cookies)

    def test_invalid_cookie_answers_with_401(self):
        """A manipulated refresh token must not produce a new access token."""
        response = self.refresh_with("kaputter-token")
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("access_token", response.cookies)

    def test_refresh_cookie_stays_untouched(self):
        """Only the access cookie is renewed, the refresh cookie stays."""
        response = self.refresh_with(self.refresh)
        self.assertNotIn("refresh_token", response.cookies)
