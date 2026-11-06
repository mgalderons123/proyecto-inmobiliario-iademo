from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection

from apps.inmuebles.models import Inmueble, Inquilino
from apps.inmuebles.services import TenantLimitReached, crear_inquilino
from apps.users.accounts import ensure_account_for_user
from apps.users.models import Cuenta, MembresiaCuenta
from apps.users.plans import approve_plan_change, request_plan_change


User = get_user_model()


@pytest.fixture
def trial_account(user):
    account = user.membresias_cuenta.get().cuenta
    account.plan = Cuenta.Planes.PRUEBA
    account.save(update_fields=["plan"])
    return account


@pytest.mark.django_db
def test_new_account_starts_on_trial_and_can_request_paid_plan():
    owner = User.objects.create_user(username="plan-owner", password="testpass123")

    account = ensure_account_for_user(
        owner,
        requested_plan=Cuenta.Planes.ESENCIAL,
    )

    assert account.plan == Cuenta.Planes.PRUEBA
    assert account.plan_solicitado == Cuenta.Planes.ESENCIAL
    assert account.plan_solicitado_por == owner
    assert account.limite_inquilinos == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("plan", "limit"),
    [
        (Cuenta.Planes.PRUEBA, 1),
        (Cuenta.Planes.ESENCIAL, 3),
        (Cuenta.Planes.PROFESIONAL, 10),
    ],
)
def test_each_plan_enforces_its_tenant_limit(user, plan, limit):
    account = user.membresias_cuenta.get().cuenta
    account.plan = plan
    account.save(update_fields=["plan"])
    for index in range(limit):
        crear_inquilino(
            nombre=f"Inquilino {index}",
            creado_por=user,
            cuenta=account,
        )

    with pytest.raises(TenantLimitReached) as exc_info:
        crear_inquilino(nombre="Sin cupo", creado_por=user, cuenta=account)

    assert exc_info.value.limit == limit
    assert account.inquilinos.count() == limit


@pytest.mark.django_db
def test_custom_plan_requires_and_enforces_positive_limit(user):
    account = user.membresias_cuenta.get().cuenta
    account.plan = Cuenta.Planes.MEDIDA
    with pytest.raises(ValidationError):
        account.full_clean()

    account.limite_inquilinos_personalizado = 2
    account.full_clean()
    account.save(update_fields=["plan", "limite_inquilinos_personalizado"])
    crear_inquilino(nombre="Uno", creado_por=user, cuenta=account)
    crear_inquilino(nombre="Dos", creado_por=user, cuenta=account)

    with pytest.raises(TenantLimitReached):
        crear_inquilino(nombre="Tres", creado_por=user, cuenta=account)


@pytest.mark.django_db
def test_only_superuser_can_approve_plan_and_downgrade_cannot_drop_below_usage(user):
    account = user.membresias_cuenta.get().cuenta
    request_plan_change(account, Cuenta.Planes.ESENCIAL, user)
    with pytest.raises(PermissionDenied):
        approve_plan_change(account, user)

    superuser = User.objects.create_superuser(
        username="plan-superuser",
        email="root@example.com",
        password="testpass123",
    )
    approved = approve_plan_change(account, superuser)
    assert approved.plan == Cuenta.Planes.ESENCIAL
    assert approved.plan_solicitado == ""
    assert approved.plan_aprobado_por == superuser

    crear_inquilino(nombre="Uno", creado_por=user, cuenta=account)
    crear_inquilino(nombre="Dos", creado_por=user, cuenta=account)
    with pytest.raises(ValueError):
        approve_plan_change(account, superuser, plan=Cuenta.Planes.PRUEBA)


@pytest.mark.django_db
def test_tenant_quota_is_shared_by_account_admins(user, trial_account):
    admin_user = User.objects.create_user(username="second-admin", password="testpass123")
    MembresiaCuenta.objects.create(
        cuenta=trial_account,
        user=admin_user,
        rol=MembresiaCuenta.Roles.ADMIN,
    )
    crear_inquilino(nombre="Primer cupo", creado_por=user, cuenta=trial_account)

    with pytest.raises(TenantLimitReached):
        crear_inquilino(
            nombre="Segundo cupo",
            creado_por=admin_user,
            cuenta=trial_account,
        )


@pytest.mark.django_db
def test_tenant_quota_is_isolated_between_accounts(user, trial_account):
    other_owner = User.objects.create_user(username="other-owner", password="testpass123")
    other_account = ensure_account_for_user(other_owner)

    crear_inquilino(nombre="Cuenta A", creado_por=user, cuenta=trial_account)
    crear_inquilino(nombre="Cuenta B", creado_por=other_owner, cuenta=other_account)

    assert trial_account.inquilinos.count() == 1
    assert other_account.inquilinos.count() == 1


@pytest.mark.django_db
def test_api_returns_conflict_when_tenant_quota_is_exhausted(jwt_client, user, trial_account):
    crear_inquilino(nombre="Cupo usado", creado_por=user, cuenta=trial_account)

    response = jwt_client.post(
        "/api/v1/inmuebles/inquilinos/",
        {"nombre": "Sin cupo"},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["detail"].code == "tenant_limit_reached"


@pytest.mark.django_db
def test_legacy_rental_payload_registers_tenant_and_respects_quota(
    jwt_client, user, trial_account
):
    property_ = Inmueble.objects.create(
        cuenta=trial_account,
        titulo="Casa",
        direccion="Calle 1",
        creado_por=user,
    )
    response = jwt_client.post(
        "/api/v1/inmuebles/contratos/",
        {
            "inmueble": property_.pk,
            "tipo": "alquiler",
            "inquilino_nombre": "Persona registrada",
            "fecha_inicio": "2026-10-10",
            "monto": "1000.00",
        },
        format="json",
    )

    assert response.status_code == 201
    tenant = Inquilino.objects.get(cuenta=trial_account)
    assert response.data["inquilino_registrado"] == tenant.pk

    other_property = Inmueble.objects.create(
        cuenta=trial_account,
        titulo="Casa 2",
        direccion="Calle 2",
        creado_por=user,
    )
    response = jwt_client.post(
        "/api/v1/inmuebles/contratos/",
        {
            "inmueble": other_property.pk,
            "tipo": "alquiler",
            "inquilino_nombre": "Persona sin cupo",
            "fecha_inicio": "2026-10-10",
            "monto": "1000.00",
        },
        format="json",
    )
    assert response.status_code == 409
    assert Inquilino.objects.filter(cuenta=trial_account).count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_tenant_creation_cannot_exceed_plan_limit():
    owner = User.objects.create_user(username="concurrent-owner", password="testpass123")
    account = ensure_account_for_user(owner)
    barrier = Barrier(2)

    def create(name):
        barrier.wait()
        try:
            try:
                crear_inquilino(nombre=name, creado_por=owner, cuenta=account)
            except TenantLimitReached:
                return "limited"
            return "created"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(create, ("Uno", "Dos")))

    assert sorted(results) == ["created", "limited"]
    assert Inquilino.objects.filter(cuenta=account).count() == 1
