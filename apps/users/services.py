import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.shortcuts import get_current_site
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation import gettext as _

User = get_user_model()

MIN_PASSWORD_LENGTH = 8
REGISTRATION_CODE_LENGTH = 6
REGISTRATION_CODE_TIMEOUT_HOURS = 24


class RegistrationError(Exception):
    def __init__(self, field, message):
        self.field = field
        self.message = message
        super().__init__(message)


def make_verification_token(user):
    signer = signing.TimestampSigner()
    return signer.sign(str(user.pk))


def verify_user(token):
    signer = signing.TimestampSigner()
    try:
        unsigned = signer.unsign(token, max_age=settings.VERIFICATION_TOKEN_TIMEOUT)
    except signing.BadSignature:
        return None
    try:
        pk = int(unsigned)
    except (ValueError, TypeError):
        return None
    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return None
    if user.is_active:
        return user
    user.is_active = True
    user.save(update_fields=["is_active"])
    return user


def _generate_registration_code():
    return "".join(secrets.choice("0123456789") for _ in range(REGISTRATION_CODE_LENGTH))


def _create_registration_code(user):
    from .models import RegistrationCode

    RegistrationCode.objects.filter(user=user).delete()
    code = _generate_registration_code()
    expires_at = timezone.now() + timedelta(hours=REGISTRATION_CODE_TIMEOUT_HOURS)
    reg_code = RegistrationCode.objects.create(
        user=user,
        code=code,
        expires_at=expires_at,
    )
    return reg_code


def send_verification_email(user, request):
    from .models import RegistrationCode, UserTheme

    token = make_verification_token(user)
    site = get_current_site(request)
    verify_url = request.build_absolute_uri(
        reverse("core:verify_email", kwargs={"token": token})
    )

    reg_code = RegistrationCode.objects.filter(user=user, used=False).first()
    if not reg_code:
        reg_code = _create_registration_code(user)

    language = (
        UserTheme.objects.filter(user=user).values_list("language", flat=True).first()
        or settings.LANGUAGE_CODE
    )
    with translation.override(language):
        subject = _("Verificá tu correo electrónico")
        message = render_to_string(
            "core/emails/verify_email.txt",
            {
                "user": user,
                "verify_url": verify_url,
                "site_name": site.name,
                "registration_code": reg_code.code,
            },
        )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])


def validate_registration_code(username, code):
    from .models import RegistrationCode

    try:
        user = User.objects.get(username__iexact=username)
    except User.DoesNotExist:
        return None, "Usuario no encontrado."

    if not user.is_active:
        return None, "Tu cuenta aún no fue verificada. Revisá tu correo."

    reg_code = RegistrationCode.objects.filter(user=user, used=False).first()
    if not reg_code:
        return None, "No tenés un código de seguridad vigente."

    if reg_code.expires_at < timezone.now():
        return None, "El código de seguridad expiró. Registrarse nuevamente."

    if reg_code.code != code:
        return None, "El código de seguridad es incorrecto."

    reg_code.used = True
    reg_code.save(update_fields=["used"])
    return user, None


@transaction.atomic
def register_user(*, username, email, password, password_confirm, requested_plan=None):
    if not username:
        raise RegistrationError("username", "Este campo es obligatorio.")
    if not email:
        raise RegistrationError("email", "Este campo es obligatorio.")
    if not password:
        raise RegistrationError("password", "Este campo es obligatorio.")

    if password != password_confirm:
        raise RegistrationError("password_confirm", "Las contraseñas no coinciden.")

    if len(password) < MIN_PASSWORD_LENGTH:
        raise RegistrationError(
            "password",
            f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.",
        )

    existing = User.objects.filter(username__iexact=username).values_list("username", flat=True)
    if username.lower() in {u.lower() for u in existing}:
        raise RegistrationError("username", "Ya existe un usuario con ese nombre de usuario.")

    existing_emails = User.objects.filter(email__iexact=email).values_list("email", flat=True)
    if email.lower() in {e.lower() for e in existing_emails}:
        raise RegistrationError("email", "Ya existe un usuario con ese email.")

    user = User.objects.create_user(
        username=username, email=email, password=password, is_active=False
    )
    from .accounts import ensure_account_for_user

    ensure_account_for_user(user, requested_plan=requested_plan)
    _create_registration_code(user)
    return user


def _generate_temp_password(length=12):
    """Generar contraseña temporal aleatoria."""
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def crear_usuario_inquilino(inquilino, request):
    """Crear usuario para un inquilino, agregarlo al grupo 'Inquilino' y enviar email de invitación.

    Retorna (user, temp_password, registration_code) o lanza ValueError.
    """
    from django.contrib.auth.models import Group
    from django.contrib.sites.shortcuts import get_current_site

    if inquilino.user:
        raise ValueError(f"El inquilino '{inquilino.nombre}' ya tiene un usuario vinculado.")

    if not inquilino.email:
        raise ValueError(f"El inquilino '{inquilino.nombre}' no tiene un email registrado.")

    # Verificar que el email no esté en uso
    if User.objects.filter(email__iexact=inquilino.email).exists():
        raise ValueError(f"Ya existe un usuario con el email '{inquilino.email}'.")

    # Generar username del email
    base_username = inquilino.email.split("@")[0]
    username = base_username
    counter = 1
    while User.objects.filter(username__iexact=username).exists():
        username = f"{base_username}{counter}"
        counter += 1

    # Generar contraseña temporal
    temp_password = _generate_temp_password()

    # Crear usuario
    user = User.objects.create_user(
        username=username,
        email=inquilino.email,
        password=temp_password,
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )

    # Agregar a grupo "Inquilino"
    inquilino_group, _ = Group.objects.get_or_create(name="Inquilino")
    user.groups.add(inquilino_group)

    from .models import MembresiaCuenta, UserSecurityState

    MembresiaCuenta.objects.update_or_create(
        cuenta=inquilino.cuenta,
        user=user,
        defaults={"rol": MembresiaCuenta.Roles.INQUILINO, "activa": True},
    )
    UserSecurityState.objects.update_or_create(
        user=user, defaults={"must_change_password": True}  # nosec B105
    )

    # Vincular inquilino
    inquilino.user = user
    inquilino.save()

    # Crear código de seguridad
    reg_code = _create_registration_code(user)

    # Enviar email de invitación
    _send_invitation_email(inquilino, user, temp_password, reg_code.code, request)

    return user, temp_password, reg_code.code


def _send_invitation_email(inquilino, user, temp_password, security_code, request):
    """Enviar email de invitación al inquilino."""
    from django.contrib.sites.shortcuts import get_current_site

    site = get_current_site(request)
    login_url = request.build_absolute_uri("/login/")

    subject = f"Invitación a {site.name}"
    message = render_to_string(
        "core/emails/invitacion_inquilino.txt",
        {
            "inquilino": inquilino,
            "user": user,
            "temp_password": temp_password,
            "security_code": security_code,
            "site_name": site.name,
            "login_url": login_url,
        },
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
