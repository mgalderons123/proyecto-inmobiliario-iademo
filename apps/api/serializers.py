from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.users.services import RegistrationError, register_user
from apps.users.models import Cuenta
from apps.users.plans import normalize_requested_plan

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "is_staff", "is_active", "date_joined")
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)
    requested_plan = serializers.ChoiceField(
        choices=(Cuenta.Planes.ESENCIAL, Cuenta.Planes.PROFESIONAL),
        required=False,
        write_only=True,
    )

    class Meta:
        model = User
        fields = ("username", "email", "password", "password_confirm", "requested_plan")

    def create(self, validated_data):
        password_confirm = validated_data.pop("password_confirm")
        try:
            return register_user(
                username=validated_data["username"],
                email=validated_data["email"],
                password=validated_data["password"],
                password_confirm=password_confirm,
                requested_plan=normalize_requested_plan(
                    validated_data.get("requested_plan")
                ),
            )
        except RegistrationError as exc:
            raise serializers.ValidationError({exc.field: exc.message})
