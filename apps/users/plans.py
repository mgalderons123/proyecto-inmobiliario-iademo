from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from .models import Cuenta


REQUESTABLE_PLANS = {
    Cuenta.Planes.ESENCIAL,
    Cuenta.Planes.PROFESIONAL,
}


def normalize_requested_plan(plan):
    return plan if plan in REQUESTABLE_PLANS else ""


def request_plan_change(account, plan, requested_by):
    plan = normalize_requested_plan(plan)
    if not plan:
        return account
    account.plan_solicitado = plan
    account.plan_solicitado_por = requested_by
    account.plan_solicitado_at = timezone.now()
    account.save(update_fields=[
        "plan_solicitado",
        "plan_solicitado_por",
        "plan_solicitado_at",
        "updated_at",
    ])
    return account


@transaction.atomic
def approve_plan_change(account, approved_by, *, plan=None, custom_limit=None):
    if not approved_by.is_superuser:
        raise PermissionDenied("Solo un superadministrador puede aprobar planes.")

    account = Cuenta.objects.select_for_update().get(pk=account.pk)
    target_plan = plan or account.plan_solicitado
    if target_plan not in Cuenta.Planes.values:
        raise ValueError("No hay un plan válido para aprobar.")

    if target_plan == Cuenta.Planes.MEDIDA:
        account.limite_inquilinos_personalizado = custom_limit
    target_limit = (
        account.limite_inquilinos_personalizado
        if target_plan == Cuenta.Planes.MEDIDA
        else Cuenta.PLAN_LIMITS[target_plan]
    )
    if not target_limit or target_limit < account.inquilinos.count():
        raise ValueError("El nuevo plan no admite los inquilinos registrados actualmente.")

    account.plan = target_plan
    account.plan_solicitado = ""
    account.plan_solicitado_por = None
    account.plan_solicitado_at = None
    account.plan_aprobado_por = approved_by
    account.plan_aprobado_at = timezone.now()
    account.save(update_fields=[
        "plan",
        "plan_solicitado",
        "limite_inquilinos_personalizado",
        "plan_solicitado_por",
        "plan_solicitado_at",
        "plan_aprobado_por",
        "plan_aprobado_at",
        "updated_at",
    ])
    return account
