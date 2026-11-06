import hashlib
import logging
import re
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction
from django.db.models import Sum
from django.http import HttpResponse, HttpResponseNotModified, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.cache import patch_cache_control
from django.utils.decorators import method_decorator
from django.utils.http import parse_etags, quote_etag
from django.utils.translation import gettext as _
from django_ratelimit.decorators import ratelimit

from apps.inmuebles.models import Contrato, Cuota, Inmueble, Inquilino, Pago
from apps.users.models import LoginLog
from apps.users.services import (
    send_verification_email,
    validate_registration_code,
    verify_user,
)

from .forms import REMEMBER_ME_DURATION, RegisterForm, RequiredPasswordChangeForm


PRIVACY_POLICY_VERSION = "temporary-2026-10"
logger = logging.getLogger(__name__)


def health(request):
    """Minimal dependency healthcheck for container orchestration."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        cache.set("healthcheck", "ok", timeout=10)
        if cache.get("healthcheck") != "ok":
            raise RuntimeError("Cache healthcheck failed")
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


@login_required
def required_password_change(request):
    from apps.users.models import UserSecurityState

    state, _created = UserSecurityState.objects.get_or_create(user=request.user)
    if not state.must_change_password:
        return redirect("core:home")

    if request.method == "POST":
        form = RequiredPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            state.must_change_password = False
            state.save(update_fields=["must_change_password", "updated_at"])
            update_session_auth_hash(request, user)
            messages.success(request, _("Contraseña actualizada. Ya podés usar la aplicación."))
            return redirect("core:home")
    else:
        form = RequiredPasswordChangeForm(request.user)
    return render(request, "core/required_password_change.html", {"form": form})


def _public_home(request):
    language = translation.get_language() or settings.LANGUAGE_CODE
    cache_key = f"public-home:{settings.PUBLIC_LANDING_CACHE_VERSION}:{language}"
    timeout = settings.PUBLIC_LANDING_CACHE_TIMEOUT
    content = None

    if timeout > 0:
        try:
            content = cache.get(cache_key)
        except Exception:
            logger.warning("Public landing cache read failed", exc_info=True)

    if content is None:
        response = render(request, "core/home.html")
        content = response.content
        if timeout > 0:
            try:
                cache.set(cache_key, content, timeout=timeout)
            except Exception:
                logger.warning("Public landing cache write failed", exc_info=True)
    else:
        response = HttpResponse(content, content_type="text/html; charset=utf-8")

    etag = quote_etag(hashlib.sha256(content).hexdigest())
    if etag in parse_etags(request.headers.get("If-None-Match", "")):
        response = HttpResponseNotModified()
    response["ETag"] = etag
    patch_cache_control(response, private=True, no_cache=True)
    return response


def home(request):
    if not request.user.is_authenticated:
        return _public_home(request)

    context = {}
    membership = getattr(request, "membership", None)
    if membership and membership.rol == "tenant":
        return redirect("inmuebles:portal")
    account = getattr(request, "cuenta", None)
    if not account:
        return render(request, "core/home.html", context)
    today = timezone.localdate()
    contracts = Contrato.objects.filter(inmueble__cuenta=account)
    properties = Inmueble.objects.filter(cuenta=account)
    overdue = Cuota.objects.filter(
        contrato__inmueble__cuenta=account,
        fecha_vencimiento__lt=today,
        estado__in=(Cuota.Estado.PENDIENTE, Cuota.Estado.VENCIDO, Cuota.Estado.PARCIAL),
    )
    overdue_totals = list(
        overdue.values("contrato__moneda")
        .annotate(total=Sum("monto") + Sum("monto_multa"))
        .order_by("contrato__moneda")
    )
    pending_payments = Pago.objects.filter(
        cuota__contrato__inmueble__cuenta=account,
        estado=Pago.Estado.PENDIENTE,
    ).select_related("cuota__contrato__inmueble")
    expiring = contracts.filter(
        estado=Contrato.Estado.ACTIVO,
        fecha_fin__gte=today,
        fecha_fin__lte=today + timedelta(days=30),
    ).select_related("inmueble").order_by("fecha_fin")
    context["inmuebles_destacados"] = properties.prefetch_related("fotos")[:6]
    context["stats"] = {
        "total_propiedades": properties.count(),
        "disponibles": properties.filter(estado=Inmueble.Estado.DISPONIBLE).count(),
        "contratos_activos": contracts.filter(estado=Contrato.Estado.ACTIVO).count(),
        "total_inquilinos": Inquilino.objects.filter(cuenta=account).distinct().count(),
        "pagos_pendientes": pending_payments.count(),
        "cuotas_vencidas": overdue.count(),
        "contratos_por_vencer": expiring.count(),
    }
    context["pending_payments"] = pending_payments[:5]
    context["expiring_contracts"] = expiring[:5]
    context["overdue_totals"] = overdue_totals
    return render(request, "core/home.html", context)


@login_required
def profile(request):
    from apps.users.models import Cuenta, MembresiaCuenta, UserTheme
    from apps.users.plans import request_plan_change

    user_theme = UserTheme.objects.get_or_create(user=request.user)[0]
    account = getattr(request, "cuenta", None)
    membership = getattr(request, "membership", None)
    can_brand_account = request.user.is_superuser or (membership and membership.is_admin)

    if request.method == "POST":
        if request.POST.get("action") == "request_plan":
            if not account or not (
                request.user.is_superuser
                or (membership and membership.rol == MembresiaCuenta.Roles.PROPIETARIO)
            ):
                raise PermissionDenied
            requested_plan = request.POST.get("requested_plan", "")
            if requested_plan not in {
                Cuenta.Planes.ESENCIAL,
                Cuenta.Planes.PROFESIONAL,
            }:
                messages.error(request, _("El plan solicitado no es válido."))
            else:
                request_plan_change(account, requested_plan, request.user)
                messages.success(request, _("Solicitud de plan enviada para aprobación."))
            return redirect("core:profile")

        # Cambiar contraseña
        if request.POST.get("action") == "change_password":
            old_password = request.POST.get("old_password", "")
            new_password1 = request.POST.get("new_password1", "")
            new_password2 = request.POST.get("new_password2", "")

            if not old_password or not new_password1 or not new_password2:
                messages.error(request, _("Todos los campos de contraseña son obligatorios."))
                return redirect("core:profile")

            if not request.user.check_password(old_password):
                messages.error(request, _("La contraseña actual es incorrecta."))
                return redirect("core:profile")

            if new_password1 != new_password2:
                messages.error(request, _("Las nuevas contraseñas no coinciden."))
                return redirect("core:profile")

            try:
                validate_password(new_password1, request.user)
            except ValidationError as exc:
                messages.error(request, " ".join(exc.messages))
                return redirect("core:profile")

            request.user.set_password(new_password1)
            request.user.save()
            update_session_auth_hash(request, request.user)
            from apps.users.models import UserSecurityState
            UserSecurityState.objects.update_or_create(
                user=request.user, defaults={"must_change_password": False}  # nosec B105
            )
            messages.success(request, _("Contraseña actualizada correctamente."))
            return redirect("core:profile")

        # Eliminar imagen de perfil
        if request.POST.get("remove_image") == "1":
            if account and can_brand_account and account.logo:
                account.logo.delete(save=False)
                account.logo = None
                account.save(update_fields=["logo"])
            elif user_theme.profile_image:
                user_theme.profile_image.delete(save=False)
                user_theme.profile_image = None
                user_theme.save()
            messages.success(request, _("Imagen de perfil eliminada."))
            return redirect("core:profile")

        # Guardar nombre del proyecto
        project_name = request.POST.get("project_name", "").strip()
        if project_name:
            user_theme.project_name = project_name
            if account and can_brand_account:
                account.nombre = project_name

        # Guardar imagen de perfil
        if "profile_image" in request.FILES:
            profile_image = request.FILES["profile_image"]
            allowed_types = ["image/jpeg", "image/png", "image/webp", "image/gif"]
            if profile_image.content_type in allowed_types:
                if account and can_brand_account:
                    if account.logo:
                        account.logo.delete(save=False)
                    account.logo = profile_image
                else:
                    if user_theme.profile_image:
                        user_theme.profile_image.delete(save=False)
                    user_theme.profile_image = profile_image
            else:
                messages.error(request, _("Formato de imagen no válido. Use JPG, PNG, WEBP o GIF."))
                return redirect("core:profile")

        lang = request.POST.get("language", "").strip()
        if lang and lang in dict(UserTheme.Languages.choices):
            user_theme.language = lang
            user_theme.save()
            translation.activate(lang)
            messages.success(request, _("Preferencia de idioma guardada."))
            response = redirect("core:profile")
            response.set_cookie("django_language", lang)
            return response

        theme = request.POST.get("theme", "").strip()
        if theme not in UserTheme.Themes.values:
            messages.error(request, _("Tema no válido."))
        else:
            if theme == UserTheme.Themes.CUSTOM:
                fields = {
                    "custom_primary",
                    "custom_primary_hover",
                    "custom_accent",
                    "custom_sidebar",
                    "custom_bg",
                    "custom_border",
                    "custom_text",
                }
                values = {name: request.POST.get(name, "").strip() for name in fields}
                if all(re.fullmatch(r"#[0-9a-fA-F]{6}", value) for value in values.values()):
                    for name, value in values.items():
                        setattr(user_theme, name, value)
                else:
                    messages.error(
                        request,
                        _("Colores personalizados no válidos: usá formato #RRGGBB en todos los campos."),
                    )
                    return redirect("core:profile")
            user_theme.theme = theme
            if account and can_brand_account:
                account.theme = theme
                if theme == UserTheme.Themes.CUSTOM:
                    for name, value in values.items():
                        setattr(account, name, value)
            user_theme.save()
            if account and can_brand_account:
                account.save()
            messages.success(request, _("Preferencia de tema guardada."))

        if project_name or "profile_image" in request.FILES:
            user_theme.save()
            if account and can_brand_account:
                account.save()
            messages.success(request, _("Personalización guardada."))
        return redirect("core:profile")

    return render(
        request,
        "core/profile.html",
        {
            "user": request.user,
            "user_theme": user_theme,
            "can_request_plan": bool(
                account
                and (
                    request.user.is_superuser
                    or (membership and membership.rol == MembresiaCuenta.Roles.PROPIETARIO)
                )
            ),
        },
    )


@ratelimit(key="ip", rate="5/m", method="POST", block=True)
def register(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            from apps.users.models import UserTheme

            language = (translation.get_language() or "es").lower().split("-")[0]
            if language not in UserTheme.Languages.values:
                language = UserTheme.Languages.ESPANOL
            UserTheme.objects.update_or_create(
                user=user,
                defaults={"language": language},
            )
            send_verification_email(user, request)
            return redirect(f"{reverse('core:home')}?registered=1")
    else:
        form = RegisterForm(initial={"requested_plan": request.GET.get("plan", "")})

    return render(request, "core/register.html", {"form": form})


def register_done(request):
    return render(request, "core/register_done.html")


def verify_email(request, token):
    user = verify_user(token)
    if user is None:
        return redirect(reverse("core:verify_done"))
    from apps.users.models import RegistrationCode

    reg_code = RegistrationCode.objects.filter(user=user, used=False).first()
    code = reg_code.code if reg_code else ""
    return redirect(f"{reverse('core:verify_done')}?valid=1&code={code}")


def verify_done(request):
    return render(request, "core/verify_done.html")


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch"
)
class CustomLoginView(LoginView):
    template_name = "core/login.html"

    def form_valid(self, form):
        security_code = self.request.POST.get("security_code", "").strip()
        user = form.get_user()

        from apps.users.models import PrivacyConsent, RegistrationCode

        has_pending_code = RegistrationCode.objects.filter(
            user=user, used=False
        ).exists()

        if has_pending_code:
            if not security_code:
                self.request.session["pending_login_user_id"] = user.pk
                self.request.session["pending_remember_me"] = self.request.POST.get("remember_me", "")
                ctx = self.get_context_data(form=form)
                ctx["needs_code"] = True
                ctx["pending_username"] = user.username
                return self.render_to_response(ctx)
            if not self.request.POST.get("privacy_consent"):
                form.add_error(
                    None,
                    _(
                        "Debés aceptar la Política de privacidad y tratamiento de datos personales para continuar."
                    ),
                )
                ctx = self.get_context_data(form=form)
                ctx["needs_code"] = True
                ctx["pending_username"] = user.username
                return self.render_to_response(ctx)

            with transaction.atomic():
                validated_user, error = validate_registration_code(user.username, security_code)
                if error:
                    form.add_error(None, error)
                    ctx = self.get_context_data(form=form)
                    ctx["needs_code"] = True
                    ctx["pending_username"] = user.username
                    return self.render_to_response(ctx)
                PrivacyConsent.objects.get_or_create(
                    user=validated_user,
                    policy_version=PRIVACY_POLICY_VERSION,
                    defaults={
                        "ip_address": self.request.META.get("REMOTE_ADDR"),
                        "user_agent": self.request.META.get("HTTP_USER_AGENT", "")[:300],
                    },
                )
            self.request.session.pop("pending_login_user_id", None)
            self.request.session.pop("pending_remember_me", None)

        remember = (
            self.request.POST.get("remember_me")
            or self.request.session.get("pending_remember_me", "")
        )
        response = super().form_valid(form)
        if remember:
            self.request.session.set_expiry(REMEMBER_ME_DURATION)
        else:
            self.request.session.set_expiry(0)

        LoginLog.objects.create(
            user=self.request.user,
            ip_address=self.request.META.get("REMOTE_ADDR"),
            user_agent=self.request.META.get("HTTP_USER_AGENT", "")[:300],
        )

        return response


@login_required
def bitacora(request):
    membership = getattr(request, "membership", None)
    if not request.user.is_superuser and not (membership and membership.is_admin):
        return redirect("core:profile")
    logs = LoginLog.objects.select_related("user")
    if not request.user.is_superuser:
        logs = logs.filter(user__membresias_cuenta__cuenta=request.cuenta)
    logs = logs.distinct()[:100]
    return render(request, "core/bitacora.html", {"logs": logs})


def _staff_required(request):
    membership = getattr(request, "membership", None)
    if not request.user.is_superuser and not (membership and membership.is_admin):
        return None
    return True


@login_required
def admin_users(request):
    membership = getattr(request, "membership", None)
    if not request.user.is_superuser and not (membership and membership.is_admin):
        return redirect("core:profile")

    from django.contrib.auth import get_user_model

    User = get_user_model()
    q = request.GET.get("q", "").strip()

    # SuperAdmin ve todos los usuarios; AdminCuenta solo ve Inquilinos
    if request.user.is_superuser:
        users = User.objects.all().select_related("registration_code").order_by("-date_joined")
    else:
        users = User.objects.filter(
            membresias_cuenta__cuenta=request.cuenta,
            membresias_cuenta__activa=True,
            is_superuser=False,
        ).select_related("registration_code").distinct().order_by("-date_joined")

    if q:
        users = users.filter(username__icontains=q) | users.filter(email__icontains=q)

    from apps.users.models import LoginLog

    last_log_map = {}
    for user in users:
        last_log = LoginLog.objects.filter(user=user).order_by("-timestamp").first()
        last_log_map[user.pk] = last_log.timestamp if last_log else None

    return render(request, "core/admin_users.html", {
        "users": users,
        "q": q,
        "last_log_map": last_log_map,
        "now": timezone.now(),
        "is_superadmin": request.user.is_superuser,
    })


@login_required
def admin_user_edit(request, pk):
    membership = getattr(request, "membership", None)
    if not request.user.is_superuser and not (membership and membership.is_admin):
        return redirect("core:profile")

    from django.contrib.auth import get_user_model
    from django.contrib import auth

    User = get_user_model()
    users = User.objects.all()
    if not request.user.is_superuser:
        users = users.filter(membresias_cuenta__cuenta=request.cuenta)
    edit_user = get_object_or_404(users.distinct(), pk=pk)

    if request.user.pk == edit_user.pk:
        return redirect("core:admin_users")

    from apps.users.models import RegistrationCode

    reg_code = RegistrationCode.objects.filter(user=edit_user).order_by("-created_at").first()

    if request.method == "POST":
        action = request.POST.get("action", "edit")

        if action == "edit":
            edit_user.email = request.POST.get("email", edit_user.email).strip()
            if request.user.is_superuser:
                edit_user.is_staff = request.POST.get("is_staff") == "on"
            try:
                edit_user.full_clean()
                fields = ["email"]
                if request.user.is_superuser:
                    fields.append("is_staff")
                edit_user.save(update_fields=fields)
                messages.success(request, f"Usuario '{edit_user.username}' actualizado.")
            except Exception as e:
                messages.error(request, f"Error al actualizar: {e}")

        elif action == "reset_password":
            new_password = request.POST.get("new_password", "").strip()
            if len(new_password) < 8:
                messages.error(request, "La contraseña debe tener al menos 8 caracteres.")
            else:
                edit_user.set_password(new_password)
                edit_user.save()
                from apps.users.models import UserSecurityState
                UserSecurityState.objects.update_or_create(
                    user=edit_user, defaults={"must_change_password": True}  # nosec B105
                )
                auth.logout(request)
                messages.success(request, f"Contraseña de '{edit_user.username}' actualizada. Tu sesión fue cerrada.")
                return redirect("core:admin_users")

        elif action == "regenerate_code":
            from apps.users.services import _create_registration_code, send_verification_email
            _create_registration_code(edit_user)
            send_verification_email(edit_user, request)
            messages.success(request, f"Nuevo código enviado a '{edit_user.username}'.")
            return redirect("core:admin_user_edit", pk=pk)

        return redirect("core:admin_user_edit", pk=pk)

    return render(request, "core/admin_user_edit.html", {
        "edit_user": edit_user,
        "reg_code": reg_code,
        "is_superadmin": request.user.is_superuser,
    })


@login_required
def admin_user_edit_email(request, pk):
    """Editar email de un usuario desde la lista (solo SuperAdmin)."""
    if not request.user.is_superuser:
        messages.error(request, "No tenés permiso para esta acción.")
        return redirect("core:admin_users")

    if request.method != "POST":
        return redirect("core:admin_users")

    from django.contrib.auth import get_user_model
    User = get_user_model()
    edit_user = get_object_or_404(User, pk=pk)

    if request.user.pk == edit_user.pk:
        messages.error(request, "No podés cambiar tu propio email desde aquí.")
        return redirect("core:admin_users")

    email = request.POST.get("email", "").strip()
    if not email:
        messages.error(request, "El email es obligatorio.")
        return redirect("core:admin_users")

    old_email = edit_user.email
    edit_user.email = email
    edit_user.save(update_fields=["email"])
    messages.success(request, f"Email de '{edit_user.username}' actualizado de '{old_email}' a '{email}'.")
    return redirect("core:admin_users")


@login_required
def admin_user_toggle_active(request, pk):
    membership = getattr(request, "membership", None)
    if not request.user.is_superuser and not (membership and membership.is_admin):
        return redirect("core:profile")

    from django.contrib.auth import get_user_model

    User = get_user_model()
    users = User.objects.all()
    if not request.user.is_superuser:
        users = users.filter(membresias_cuenta__cuenta=request.cuenta)
    edit_user = get_object_or_404(users.distinct(), pk=pk)

    if request.method == "POST" and request.user.pk != edit_user.pk:
        if request.user.is_superuser:
            edit_user.is_active = not edit_user.is_active
            edit_user.save(update_fields=["is_active"])
            active = edit_user.is_active
        else:
            from apps.users.models import MembresiaCuenta
            target_membership = get_object_or_404(
                MembresiaCuenta, cuenta=request.cuenta, user=edit_user
            )
            target_membership.activa = not target_membership.activa
            target_membership.save(update_fields=["activa"])
            active = target_membership.activa
        estado = "activado" if active else "desactivado"
        messages.success(request, f"Usuario '{edit_user.username}' {estado}.")

    return redirect("core:admin_users")


@login_required
def admin_user_delete(request, pk):
    membership = getattr(request, "membership", None)
    if not request.user.is_superuser and not (membership and membership.is_admin):
        return redirect("core:profile")

    from django.contrib.auth import get_user_model

    User = get_user_model()
    users = User.objects.all()
    if not request.user.is_superuser:
        users = users.filter(membresias_cuenta__cuenta=request.cuenta)
    edit_user = get_object_or_404(users.distinct(), pk=pk)

    if request.method == "POST" and request.user.pk != edit_user.pk:
        # AdminCuenta solo puede eliminar Inquilinos
        if not request.user.is_superuser and not edit_user.groups.filter(name="Inquilino").exists():
            messages.error(request, "No tenés permiso para eliminar este usuario.")
            return redirect("core:admin_users")

        username = edit_user.username
        try:
            if request.user.is_superuser:
                edit_user.delete()
                message = f"Usuario '{username}' eliminado."
            else:
                from apps.users.models import MembresiaCuenta
                MembresiaCuenta.objects.filter(
                    cuenta=request.cuenta, user=edit_user
                ).delete()
                message = f"Acceso de '{username}' eliminado de la cuenta."
            messages.success(request, message)
        except Exception as e:
            messages.error(request, f"Error al eliminar: {e}")

    return redirect("core:admin_users")
