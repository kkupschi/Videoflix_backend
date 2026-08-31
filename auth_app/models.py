"""Database models for user accounts."""
from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """User account that is identified by a unique email address.

    The username field is kept so the Docker entrypoint can create the
    superuser with a username. Registration stores the email address in
    both fields, which keeps the username unique as well.
    """

    email = models.EmailField(unique=True)

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        """Return the email address as readable representation."""
        return self.email
