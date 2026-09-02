"""Views for the authentication endpoints."""
from rest_framework.status import (
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..utils import (
    ACTIVATION_FAILED,
    ACTIVATION_SUCCESS,
    LOGOUT_SUCCESS,
    REFRESH_INVALID,
    REFRESH_MISSING,
    activate_user,
    blacklist_refresh_token,
    build_login_response,
    build_refresh_response,
    build_registration_response,
    create_activation_token,
    create_token_pair,
    delete_auth_cookies,
    error_response,
    get_refresh_cookie,
    get_user_by_uidb64,
    is_activation_valid,
    queue_activation_email,
    refresh_access_token,
    set_access_cookie,
    set_auth_cookies,
)
from .serializers import LoginSerializer, RegistrationSerializer


class RegistrationView(APIView):
    """Create an inactive account and trigger the activation mail."""

    permission_classes = [AllowAny]

    def post(self, request):
        """Register a new user and return the account with its token."""
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token = create_activation_token(user)
        queue_activation_email(user, token)
        return Response(
            build_registration_response(user, token),
            status=HTTP_201_CREATED,
        )


class ActivationView(APIView):
    """Unlock an account with the link from the activation mail."""

    permission_classes = [AllowAny]

    def get(self, request, uidb64, token):
        """Confirm the token and switch the account to active."""
        user = get_user_by_uidb64(uidb64)
        if not is_activation_valid(user, token):
            body = {"message": ACTIVATION_FAILED}
            return Response(body, status=HTTP_400_BAD_REQUEST)
        activate_user(user)
        return Response({"message": ACTIVATION_SUCCESS})


class LoginView(APIView):
    """Authenticate an account and store the tokens in HttpOnly cookies."""

    permission_classes = [AllowAny]

    def post(self, request):
        """Check the credentials and answer with the token cookies."""
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh, access = create_token_pair(user)
        response = Response(build_login_response(user))
        return set_auth_cookies(response, access, refresh)


class TokenRefreshView(APIView):
    """Issue a new access token based on the refresh token cookie."""

    permission_classes = [AllowAny]

    def post(self, request):
        """Return a fresh access token and update its cookie."""
        raw_refresh = get_refresh_cookie(request)
        if not raw_refresh:
            return error_response(REFRESH_MISSING, HTTP_400_BAD_REQUEST)
        access = refresh_access_token(raw_refresh)
        if access is None:
            return error_response(REFRESH_INVALID, HTTP_401_UNAUTHORIZED)
        response = Response(build_refresh_response(access))
        return set_access_cookie(response, access)


class LogoutView(APIView):
    """End a session by invalidating the refresh token."""

    permission_classes = [AllowAny]

    def post(self, request):
        """Blacklist the refresh token and clear both cookies."""
        raw_refresh = get_refresh_cookie(request)
        if not raw_refresh:
            return error_response(REFRESH_MISSING, HTTP_400_BAD_REQUEST)
        blacklist_refresh_token(raw_refresh)
        response = Response({"detail": LOGOUT_SUCCESS})
        return delete_auth_cookies(response)
