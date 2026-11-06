from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError

from apps.users.models import Cuenta, LoginLog, RegistrationCode, UserTheme
from apps.users.plans import normalize_requested_plan

User = get_user_model()

REMEMBER_ME_DURATION = timedelta(days=7)


def _delete_inactive_user(user):
    RegistrationCode.objects.filter(user=user).delete()
    LoginLog.objects.filter(user=user).delete()
    UserTheme.objects.filter(user=user).delete()
    user.delete()


class RegisterForm(UserCreationForm):
    requested_plan = forms.ChoiceField(
        choices=[("", "Prueba")] + [
            (Cuenta.Planes.ESENCIAL, "Esencial"),
            (Cuenta.Planes.PROFESIONAL, "Profesional"),
        ],
        required=False,
        widget=forms.HiddenInput,
    )
    email = forms.EmailField(
        label="Correo electrónico",
        required=True,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Contraseña"
        self.fields["password2"].label = "Repetir contraseña"
        self.fields["password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["password2"].widget.attrs["autocomplete"] = "new-password"

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_active = False
        if commit:
            user.save()
            from apps.users.accounts import ensure_account_for_user

            ensure_account_for_user(
                user,
                requested_plan=normalize_requested_plan(
                    self.cleaned_data.get("requested_plan")
                ),
            )
        return user

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        existing = User.objects.filter(username__iexact=username).first()
        if existing:
            if existing.is_active:
                raise ValidationError("Ya existe un usuario con ese nombre de usuario.")
            _delete_inactive_user(existing)
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip()
        from apps.inmuebles.models import Inquilino
        inquilino = Inquilino.objects.filter(email__iexact=email, user__isnull=False).first()
        if inquilino:
            raise ValidationError(
                "Este correo pertenece a un inquilino. Contacte al administrador."
            )
        existing = User.objects.filter(email__iexact=email).first()
        if existing:
            if existing.is_active:
                raise ValidationError("Ya existe un usuario con ese email.")
            _delete_inactive_user(existing)
        return email


class RequiredPasswordChangeForm(PasswordChangeForm):
    def clean_new_password2(self):
        password = self.cleaned_data.get("new_password2")
        if password and self.user.check_password(password):
            raise ValidationError("La nueva contraseña debe ser diferente de la temporal.")
        return password
