from django.db import transaction


@transaction.atomic
def ensure_account_for_user(user, *, name=None, requested_plan=None):
    """Return the user's first administrative account, creating one when needed."""
    from .models import Cuenta, MembresiaCuenta

    membership = (
        MembresiaCuenta.objects.select_related("cuenta")
        .filter(
            user=user,
            activa=True,
            cuenta__activa=True,
            rol__in=(MembresiaCuenta.Roles.PROPIETARIO, MembresiaCuenta.Roles.ADMIN),
        )
        .order_by("created_at", "pk")
        .first()
    )
    if membership:
        if requested_plan:
            from .plans import request_plan_change

            request_plan_change(membership.cuenta, requested_plan, user)
        return membership.cuenta

    account = Cuenta.objects.create(
        nombre=name or user.get_full_name() or user.username or "Nueva cuenta"
    )
    MembresiaCuenta.objects.create(
        cuenta=account,
        user=user,
        rol=MembresiaCuenta.Roles.PROPIETARIO,
    )
    if requested_plan:
        from .plans import request_plan_change

        request_plan_change(account, requested_plan, user)
    return account


def get_active_membership(user, account_id=None):
    from .models import MembresiaCuenta

    if not user or not user.is_authenticated:
        return None

    memberships = MembresiaCuenta.objects.select_related("cuenta").filter(
        user=user, activa=True, cuenta__activa=True
    )
    if account_id:
        membership = memberships.filter(cuenta_id=account_id).first()
        if membership:
            return membership
    return memberships.order_by("created_at", "pk").first()


def get_request_account(request):
    return getattr(request, "cuenta", None)


def user_can_administer(user, account):
    from .models import MembresiaCuenta

    if not user or not user.is_authenticated or not account:
        return False
    if user.is_superuser:
        return True
    return MembresiaCuenta.objects.filter(
        user=user,
        cuenta=account,
        activa=True,
        rol__in=(MembresiaCuenta.Roles.PROPIETARIO, MembresiaCuenta.Roles.ADMIN),
    ).exists()
