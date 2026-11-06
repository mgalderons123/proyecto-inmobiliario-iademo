from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.currencies import CURRENCY_CHOICES


class Cuenta(models.Model):
    class Planes(models.TextChoices):
        PRUEBA = "trial", "Prueba"
        ESENCIAL = "essential", "Esencial"
        PROFESIONAL = "professional", "Profesional"
        MEDIDA = "custom", "A medida"

    PLAN_LIMITS = {
        Planes.PRUEBA: 1,
        Planes.ESENCIAL: 3,
        Planes.PROFESIONAL: 10,
    }

    class Themes(models.TextChoices):
        DEFAULT = "default", "Teal Profesional"
        NAVY = "navy", "Navy & Oro"
        INDIGO = "indigo", "Índigo Confianza"
        EMERALD = "emerald", "Verde Esmeralda"
        VIOLET = "violet", "Violeta Creativo"
        CUSTOM = "custom", "Personalizada"

    class Locales(models.TextChoices):
        ES_AR = "es-AR", "Español (Argentina)"
        ES_MX = "es-MX", "Español (México)"
        EN_US = "en-US", "English (United States)"
        PT_BR = "pt-BR", "Português (Brasil)"

    nombre = models.CharField(max_length=120)
    moneda_predeterminada = models.CharField(
        max_length=3, choices=CURRENCY_CHOICES, default="USD"
    )
    locale = models.CharField(
        max_length=10, choices=Locales.choices, default=Locales.ES_AR
    )
    zona_horaria = models.CharField(
        max_length=64, default="America/Argentina/Buenos_Aires"
    )
    theme = models.CharField(max_length=12, choices=Themes.choices, default=Themes.DEFAULT)
    logo = models.ImageField(upload_to="account_logos/%Y/%m/", blank=True)
    custom_primary = models.CharField(max_length=7, blank=True, default="")
    custom_primary_hover = models.CharField(max_length=7, blank=True, default="")
    custom_accent = models.CharField(max_length=7, blank=True, default="")
    custom_sidebar = models.CharField(max_length=7, blank=True, default="")
    custom_bg = models.CharField(max_length=7, blank=True, default="")
    custom_border = models.CharField(max_length=7, blank=True, default="")
    custom_text = models.CharField(max_length=7, blank=True, default="")
    plan = models.CharField(
        max_length=16, choices=Planes.choices, default=Planes.PRUEBA
    )
    plan_solicitado = models.CharField(
        max_length=16, choices=Planes.choices, blank=True, default=""
    )
    limite_inquilinos_personalizado = models.PositiveIntegerField(
        null=True, blank=True
    )
    plan_solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planes_solicitados",
    )
    plan_solicitado_at = models.DateTimeField(null=True, blank=True)
    plan_aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planes_aprobados",
    )
    plan_aprobado_at = models.DateTimeField(null=True, blank=True)
    activa = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nombre", "pk"]

    def __str__(self):
        return self.nombre

    @property
    def limite_inquilinos(self):
        if self.plan == self.Planes.MEDIDA:
            return self.limite_inquilinos_personalizado or 0
        return self.PLAN_LIMITS[self.plan]

    @property
    def inquilinos_utilizados(self):
        return self.inquilinos.count()

    @property
    def inquilinos_disponibles(self):
        return max(self.limite_inquilinos - self.inquilinos_utilizados, 0)

    @property
    def puede_crear_inquilino(self):
        return self.inquilinos_utilizados < self.limite_inquilinos

    def clean(self):
        super().clean()
        if self.plan == self.Planes.MEDIDA and not self.limite_inquilinos_personalizado:
            raise ValidationError({
                "limite_inquilinos_personalizado":
                    "El plan A medida requiere un límite de inquilinos positivo."
            })
        if self.pk and self.limite_inquilinos < self.inquilinos_utilizados:
            raise ValidationError({
                "plan": "El plan no puede admitir menos inquilinos que los registrados actualmente."
            })

    @property
    def custom_css(self):
        if self.theme != self.Themes.CUSTOM:
            return ""
        values = (
            self.custom_primary,
            self.custom_primary_hover,
            self.custom_accent,
            self.custom_sidebar,
            self.custom_bg,
            self.custom_border,
            self.custom_text,
        )
        if not all(len(value) == 7 and value.startswith("#") for value in values):
            return ""
        return (
            'html[data-theme="custom"]{'
            f"--color-primary:{self.custom_primary};"
            f"--color-primary-hover:{self.custom_primary_hover};"
            f"--color-accent:{self.custom_accent};"
            f"--color-sidebar:{self.custom_sidebar};"
            f"--color-bg:{self.custom_bg};"
            f"--color-border:{self.custom_border};"
            f"--color-text:{self.custom_text};"
            "}"
        )


class MembresiaCuenta(models.Model):
    class Roles(models.TextChoices):
        PROPIETARIO = "owner", "Propietario de cuenta"
        ADMIN = "admin", "Administrador"
        INQUILINO = "tenant", "Inquilino"

    cuenta = models.ForeignKey(
        Cuenta, on_delete=models.CASCADE, related_name="membresias"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="membresias_cuenta",
    )
    rol = models.CharField(max_length=12, choices=Roles.choices)
    activa = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cuenta", "user"], name="unique_cuenta_user_membership"
            )
        ]
        indexes = [
            models.Index(fields=["user", "activa"]),
            models.Index(fields=["cuenta", "rol", "activa"]),
        ]

    @property
    def is_admin(self):
        return self.rol in {self.Roles.PROPIETARIO, self.Roles.ADMIN}

    def clean(self):
        if not self.cuenta.activa and self.activa:
            raise ValidationError("No se puede activar una membresía de una cuenta inactiva.")

    def __str__(self):
        return f"{self.user} - {self.cuenta} ({self.get_rol_display()})"


class RegistrationCode(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="registration_code",
    )
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    class Meta:
        db_table = "registration_codes"

    def __str__(self):
        return f"Codigo para {self.user.username}"


class LoginLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="login_logs",
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        db_table = "login_logs"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.user.username} @ {self.timestamp}"


class PrivacyConsent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="privacy_consents",
    )
    policy_version = models.CharField(max_length=32)
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        db_table = "privacy_consents"
        ordering = ["-accepted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "policy_version"],
                name="unique_user_privacy_policy_version",
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.policy_version}"


class UserSecurityState(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="security_state",
    )
    must_change_password = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Seguridad de {self.user.username}"


class UserTheme(models.Model):
    class Themes(models.TextChoices):
        DEFAULT = "default", "Teal Profesional"
        NAVY = "navy", "Navy & Oro"
        INDIGO = "indigo", "Índigo Confianza"
        EMERALD = "emerald", "Verde Esmeralda"
        VIOLET = "violet", "Violeta Creativo"
        CUSTOM = "custom", "Personalizada"

    class Languages(models.TextChoices):
        ESPANOL = "es", "Español"
        INGLES = "en", "English"
        PORTUGUES = "pt", "Português"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_theme",
    )
    theme = models.CharField(
        max_length=12, choices=Themes.choices, default=Themes.DEFAULT
    )
    language = models.CharField(
        max_length=5, choices=Languages.choices, default=Languages.ESPANOL
    )
    custom_primary = models.CharField(max_length=7, blank=True, default="")
    custom_primary_hover = models.CharField(max_length=7, blank=True, default="")
    custom_accent = models.CharField(max_length=7, blank=True, default="")
    custom_sidebar = models.CharField(max_length=7, blank=True, default="")
    custom_bg = models.CharField(max_length=7, blank=True, default="")
    custom_border = models.CharField(max_length=7, blank=True, default="")
    custom_text = models.CharField(max_length=7, blank=True, default="")
    project_name = models.CharField(
        max_length=50,
        default="Casarent App",
        blank=True,
        verbose_name="Nombre del proyecto",
    )
    profile_image = models.ImageField(
        upload_to="profile_images/%Y/%m/",
        blank=True,
        verbose_name="Imagen de perfil",
    )

    class Meta:
        db_table = "user_themes"

    def __str__(self):
        return f"Tema de {self.user.username}: {self.theme}"

    @property
    def custom_css(self):
        """CSS inline que aplica los colores personalizados sobre :root."""
        if self.theme != self.Themes.CUSTOM:
            return ""
        try:
            r = int(self.custom_primary[1:3], 16)
            g = int(self.custom_primary[3:5], 16)
            b = int(self.custom_primary[5:7], 16)
        except (ValueError, IndexError):
            return ""
        return (
            "html[data-theme=\"custom\"]{"
            f"--color-primary:{self.custom_primary};"
            f"--color-primary-hover:{self.custom_primary_hover};"
            f"--color-primary-light:rgba({r},{g},{b},0.12);"
            f"--color-accent:{self.custom_accent};"
            f"--color-ring:{self.custom_primary};"
            f"--color-sidebar:{self.custom_sidebar};"
            f"--color-bg:{self.custom_bg};"
            f"--color-border:{self.custom_border};"
            f"--color-text:{self.custom_text};"
            "}"
        )
