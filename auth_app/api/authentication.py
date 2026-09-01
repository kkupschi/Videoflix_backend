"""Authentication that reads the access token from an HttpOnly cookie."""
from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """Take the access token from the cookie instead of the header.

    The frontend never sees the token, because the cookie is marked as
    HttpOnly. Scripts in the browser can therefore not read it.
    """

    def authenticate(self, request):
        """Return the account behind the cookie or None if there is none."""
        raw_token = request.COOKIES.get(settings.JWT_ACCESS_COOKIE)
        if not raw_token:
            return None
        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token
