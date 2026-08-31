"""Views for the authentication endpoints."""
from django.contrib.auth.tokens import default_token_generator
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..utils import build_registration_response, queue_activation_email
from .serializers import RegistrationSerializer


class RegistrationView(APIView):
    """Create an inactive account and trigger the activation mail."""

    permission_classes = [AllowAny]

    def post(self, request):
        """Register a new user and return the account with its token."""
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token = default_token_generator.make_token(user)
        queue_activation_email(user, token)
        return Response(
            build_registration_response(user, token),
            status=status.HTTP_201_CREATED,
        )
