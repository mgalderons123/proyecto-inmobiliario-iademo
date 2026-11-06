import logging
import traceback

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils import translation

logger = logging.getLogger(__name__)


class ExceptionLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        logger.error(
            "Unhandled exception for %s %s\n%s",
            request.method,
            request.build_absolute_uri(),
            traceback.format_exc(),
        )


class UserProfileLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = None
        if request.user.is_authenticated:
            try:
                from apps.users.models import UserTheme
                theme = UserTheme.objects.get(user=request.user)
                lang = theme.language
            except UserTheme.DoesNotExist:
                pass
        if not lang:
            lang = request.COOKIES.get("django_language") or getattr(
                request, "LANGUAGE_CODE", settings.LANGUAGE_CODE
            )
        lang = lang.lower().split("-")[0]
        if lang not in dict(settings.LANGUAGES):
            lang = settings.LANGUAGE_CODE
        translation.activate(lang)
        request.LANGUAGE_CODE = translation.get_language()
        response = self.get_response(request)
        return response


class AccountContextMiddleware:
    """Resolve the selected account once for all web and API views."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.cuenta = None
        request.membership = None
        if request.user.is_authenticated:
            from apps.users.accounts import get_active_membership
            from apps.users.models import Cuenta

            account_id = request.session.get("active_account_id")
            membership = get_active_membership(request.user, account_id)
            if membership:
                request.membership = membership
                request.cuenta = membership.cuenta
                request.session["active_account_id"] = membership.cuenta_id
            elif request.user.is_superuser:
                request.cuenta = Cuenta.objects.filter(activa=True).order_by("pk").first()
        if request.user.is_authenticated and not request.user.is_superuser:
            path = request.path
            is_portal = path.startswith("/inmuebles/mi-portal/") or path == "/inmuebles/mi-portal/"
            is_management = path.startswith("/inmuebles/") or path.startswith("/api/v1/inmuebles/")
            if is_management and not is_portal:
                if not request.membership or not request.membership.is_admin:
                    raise PermissionDenied
        return self.get_response(request)


class ForcePasswordChangeMiddleware:
    allowed_prefixes = (
        "/change-temporary-password/",
        "/logout/",
        "/password_reset/",
        "/reset/",
        "/static/",
        "/health/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.path.startswith(self.allowed_prefixes):
            from apps.users.models import UserSecurityState

            if UserSecurityState.objects.filter(
                user=request.user, must_change_password=True
            ).exists():
                return redirect("core:required_password_change")
        return self.get_response(request)
