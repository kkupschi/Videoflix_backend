"""Serializers for the authentication endpoints."""
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

from ..models import CustomUser
from ..utils import authenticate_by_email

GENERIC_INPUT_ERROR = "Please check your entries and try again."


class RegistrationSerializer(serializers.ModelSerializer):
    """Validate the registration payload and create an inactive account."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    confirmed_password = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ["id", "email", "password", "confirmed_password"]

    def validate_email(self, value):
        """Reject a known address without revealing that it is taken."""
        if CustomUser.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(GENERIC_INPUT_ERROR)
        return value.lower()

    def validate(self, attrs):
        """Check that both passwords match and follow the password policy."""
        if attrs["password"] != attrs["confirmed_password"]:
            raise serializers.ValidationError(
                {"confirmed_password": GENERIC_INPUT_ERROR}
            )
        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        """Store the account in an inactive state until it is activated."""
        email = validated_data["email"]
        user = CustomUser(username=email, email=email, is_active=False)
        user.set_password(validated_data["password"])
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    """Check the credentials of a login request."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        """Attach the account when address and password fit together."""
        user = authenticate_by_email(attrs["email"], attrs["password"])
        if user is None:
            raise AuthenticationFailed(GENERIC_INPUT_ERROR)
        attrs["user"] = user
        return attrs
