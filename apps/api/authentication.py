from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class PasswordChangeJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, token = result
        from apps.users.accounts import get_active_membership
        from apps.users.models import UserSecurityState

        if UserSecurityState.objects.filter(
            user=user, must_change_password=True
        ).exists():
            raise AuthenticationFailed(
                "Debe cambiar la contraseña temporal antes de usar la API.",
                code="password_change_required",
            )
        account_id = request.headers.get("X-Account-ID")
        membership = get_active_membership(user, account_id)
        if account_id and membership and str(membership.cuenta_id) != str(account_id):
            membership = None
        request.membership = membership
        request.cuenta = membership.cuenta if membership else None
        if user.is_superuser and request.cuenta is None:
            from apps.users.models import Cuenta

            accounts = Cuenta.objects.filter(activa=True)
            request.cuenta = accounts.filter(pk=account_id).first() if account_id else accounts.order_by("pk").first()
        return user, token
