from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """The authenticated user's own record."""

    is_creator = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "role",
            "role_chosen",
            "is_creator",
            "display_name",
            "bio",
            "avatar_url",
            "date_joined",
        )
        read_only_fields = fields


class PublicUserSerializer(serializers.ModelSerializer):
    """Creator chip shown on public session cards - no email, no role internals."""

    display_name = serializers.CharField(source="public_name", read_only=True)

    class Meta:
        model = User
        fields = ("id", "display_name", "avatar_url")
        read_only_fields = fields


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Whitelist for PATCH /api/me/.

    Only these three fields exist here on purpose: a client that posts
    ``{"role": "CREATOR"}`` or ``{"is_staff": true}`` gets those keys ignored
    rather than applied. Privilege changes go through their own endpoint.
    """

    class Meta:
        model = User
        fields = ("display_name", "bio", "avatar_url")

    def validate_display_name(self, value: str) -> str:
        value = value.strip()
        if len(value) > 100:
            raise serializers.ValidationError("Display name must be 100 characters or fewer.")
        return value

    def validate_bio(self, value: str) -> str:
        if len(value) > 1000:
            raise serializers.ValidationError("Bio must be 1000 characters or fewer.")
        return value.strip()


class ChooseRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.Role.choices)


class GitHubCodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=512)


class AuthResponseSerializer(serializers.Serializer):
    """Documented shape of the OAuth response (used by drf-spectacular)."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    is_new_user = serializers.BooleanField()
    user = UserSerializer()
