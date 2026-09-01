"""Views for the authentication endpoints."""
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..utils import (
    ACTIVATION_FAILED,
    ACTIVATION_SUCCESS,
    activate_user,
    build_registration_response,
    create_activation_token,
    get_user_by_uidb64,
    is_activation_valid,
    queue_activation_email,
)
from .serializers import RegistrationSerializer


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
            status=status.HTTP_201_CREATED,
        )


class ActivationView(APIView):
    """Unlock an account with the link from the activation mail."""

    permission_classes = [AllowAny]

    def get(self, request, uidb64, token):
        """Confirm the token and switch the account to active."""
        user = get_user_by_uidb64(uidb64)
        if not is_activation_valid(user, token):
            return Response(
                {"message": ACTIVATION_FAILED},
                status=status.HTTP_400_BAD_REQUEST,
            )
        activate_user(user)
        return Response({"message": ACTIVATION_SUCCESS})
