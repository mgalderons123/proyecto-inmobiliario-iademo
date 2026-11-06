"""Regression coverage for production data integrity and concurrent writers."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier

import pytest
from django.db import close_old_connections, connection, connections

from apps.inmuebles.models import Contrato, Cuota, Inmueble, Inquilino, Pago
from apps.inmuebles.services import (
    ContratoError, PagoError, crear_contrato, generar_cuota_mensual, registrar_pago,
)
from apps.users.models import MembresiaCuenta


def make_property(user):
    return Inmueble.objects.create(
        cuenta=user.membresias_cuenta.get().cuenta,
        titulo="Production regression", direccion="Test address", creado_por=user,
    )


def make_contract(user):
    return Contrato.objects.create(
        inmueble=make_property(user), tipo=Contrato.Tipo.ALQUILER,
        fecha_inicio=date.today(), monto=Decimal("100"), creado_por=user,
    )


@pytest.mark.django_db
def test_saving_tenant_preserves_existing_owner_membership(user):
    membership = user.membresias_cuenta.get()
    tenant = Inquilino.objects.create(
        cuenta=membership.cuenta, user=user, nombre="Owner tenant", creado_por=user,
    )
    tenant.save()
    membership.refresh_from_db()
    assert membership.rol == MembresiaCuenta.Roles.PROPIETARIO


@pytest.mark.django_db
def test_generic_api_cannot_edit_paid_installment(jwt_client, user):
    cuota = Cuota.objects.create(
        contrato=make_contract(user), numero=1, fecha_vencimiento=date.today(),
        monto=100, estado=Cuota.Estado.PAGADO,
    )
    response = jwt_client.patch(
        f"/api/v1/inmuebles/cuotas/{cuota.pk}/", {"monto": "1.00"}, format="json",
    )
    assert response.status_code == 400
    cuota.refresh_from_db()
    assert cuota.monto == 100


@pytest.mark.django_db
def test_generic_api_cannot_move_installment(jwt_client, user):
    cuota = Cuota.objects.create(
        contrato=make_contract(user), numero=1, fecha_vencimiento=date.today(), monto=100,
    )
    response = jwt_client.patch(
        f"/api/v1/inmuebles/cuotas/{cuota.pk}/", {"numero": 99}, format="json",
    )
    assert response.status_code == 400
    cuota.refresh_from_db()
    assert cuota.numero == 1


def concurrently(operation):
    barrier = Barrier(2)

    def run():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return operation()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run) for _ in range(2)]
        return [future.result(timeout=20) for future in futures]


@pytest.mark.django_db(transaction=True)
def test_concurrent_payments_cannot_exceed_balance(user):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    cuota = Cuota.objects.create(
        contrato=make_contract(user), numero=1, fecha_vencimiento=date.today(), monto=100,
    )

    def pay():
        try:
            registrar_pago(
                cuota=Cuota.objects.get(pk=cuota.pk), monto=Decimal("75"),
                fecha_pago=date.today(), metodo_pago="efectivo", creado_por=user,
            )
            return "created"
        except PagoError:
            return "rejected"

    assert sorted(concurrently(pay)) == ["created", "rejected"]
    assert Pago.objects.filter(cuota=cuota).count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_contracts_cannot_double_rent(user):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    inmueble = make_property(user)
    tenant = Inquilino.objects.create(
        cuenta=inmueble.cuenta, nombre="Tenant", creado_por=user,
    )

    def rent():
        try:
            crear_contrato(
                inmueble=Inmueble.objects.get(pk=inmueble.pk), tipo=Contrato.Tipo.ALQUILER,
                inquilino_registrado=tenant, fecha_inicio=date.today(), monto=100,
                creado_por=user,
            )
            return "created"
        except ContratoError:
            return "rejected"

    assert sorted(concurrently(rent)) == ["created", "rejected"]
    assert inmueble.contratos.count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_installments_allocate_distinct_numbers(user):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    contrato = make_contract(user)

    def generate():
        return generar_cuota_mensual(
            contrato=Contrato.objects.get(pk=contrato.pk), creado_por=user,
        ).numero

    assert sorted(concurrently(generate)) == [1, 2]


@pytest.mark.django_db(transaction=True)
def test_geocoding_does_not_hold_a_service_transaction(user, monkeypatch):
    from apps.inmuebles import services

    calls = []

    def geocode(address):
        calls.append(address)
        assert not connection.in_atomic_block
        return 1, 2, address

    monkeypatch.setattr(services, 'geocode_address', geocode)
    inmueble = services.crear_inmueble(
        titulo='Geo test', direccion='First address', creado_por=user,
    )
    services.actualizar_inmueble(inmueble, direccion='Second address')
    assert calls == ['First address', 'Second address']
