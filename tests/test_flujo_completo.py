import pytest
from datetime import date
from decimal import Decimal

from apps.inmuebles.models import Contrato, Cuota, Inmueble, Pago, Recibo
from apps.inmuebles.services import (
    aplicar_multa,
    aprobar_pago,
    crear_contrato,
    crear_inmueble,
    crear_inquilino,
    crear_cuota_personalizada,
    generar_cuota_mensual,
    registrar_pago,
    rechazar_pago,
    renovar_contrato,
    rescindir_contrato,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def mock_geocode(mocker):
    return mocker.patch(
        "apps.inmuebles.services.geocode_address",
        return_value=(-34.603722, -58.381592, "Av. Siempre Viva 123, Buenos Aires, Argentina"),
    )


# ---------------------------------------------------------------------------
# Test 1 — Flujo completo alquiler: pago total, recibo generado
# ---------------------------------------------------------------------------
class TestFlujoAlquilerPagoTotal:
    def test_flujo_completo(self, user, mock_geocode):
        # 1. Crear inmueble
        inmueble = crear_inmueble(
            titulo="Casa San Martín",
            direccion="Av. Siempre Viva 123",
            creado_por=user,
            precio=80000,
            tipo="casa",
            habitaciones=3,
            banos=2,
        )
        assert inmueble.estado == Inmueble.Estado.DISPONIBLE

        # 2. Crear contrato de alquiler
        contrato = crear_contrato(
            inmueble=inmueble,
            tipo="alquiler",
            creado_por=user,
            inquilino_nombre="Carlos Pérez",
            inquilino_email="carlos@test.com",
            inquilino_telefono="1155551234",
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
            monto=80000,
        )
        assert contrato.estado == Contrato.Estado.ACTIVO
        inmueble.refresh_from_db()
        assert inmueble.estado == Inmueble.Estado.ALQUILADO

        # 3. Generar cuota mensual
        cuota = generar_cuota_mensual(contrato=contrato, creado_por=user)
        assert cuota.monto == Decimal("80000.00")
        assert cuota.estado == Cuota.Estado.PENDIENTE

        # 4. Registrar pago y aprobar
        pago = registrar_pago(
            cuota=cuota,
            monto=80000,
            fecha_pago=date(2026, 1, 15),
            metodo_pago="transferencia",
            creado_por=user,
        )
        assert pago.estado == Pago.Estado.PENDIENTE

        pago_aprobado = aprobar_pago(pago)
        assert pago_aprobado.estado == Pago.Estado.APROBADO
        cuota.refresh_from_db()
        assert cuota.estado == Cuota.Estado.PAGADO

        # 5. Verificar recibo
        recibo = Recibo.objects.get(pago=pago_aprobado)
        assert recibo.codigo.startswith("REC-")


# ---------------------------------------------------------------------------
# Test 2 — Alquiler con inquilino registrado en DB
# ---------------------------------------------------------------------------
class TestAlquilerInquilinoRegistrado:
    def test_inquilino_registrado(self, user, mock_geocode):
        inquilino = crear_inquilino(
            nombre="María González",
            creado_por=user,
            email="maria@test.com",
            telefono="1166662345",
            documento="30123456",
        )
        inmueble = crear_inmueble(
            titulo="Dpto Centro",
            direccion="Av. Siempre Viva 123",
            creado_por=user,
            tipo="dpto",
            precio=60000,
        )
        contrato = crear_contrato(
            inmueble=inmueble,
            tipo="alquiler",
            creado_por=user,
            inquilino_registrado=inquilino,
            fecha_inicio=date(2026, 3, 1),
            fecha_fin=date(2027, 2, 28),
            monto=60000,
        )
        assert contrato.inquilino_registrado == inquilino
        assert contrato.inquilino_nombre == ""

        cuota = generar_cuota_mensual(contrato=contrato, creado_por=user)
        pago = registrar_pago(
            cuota=cuota,
            monto=60000,
            fecha_pago=date(2026, 3, 10),
            metodo_pago="efectivo",
            creado_por=user,
        )
        aprobar_pago(pago)
        cuota.refresh_from_db()
        assert cuota.estado == Cuota.Estado.PAGADO


# ---------------------------------------------------------------------------
# Test 3 — Alquiler por habitaciones, 2 contratos, pagos parciales
# ---------------------------------------------------------------------------
class TestAlquilerPorHabitaciones:
    def test_dos_contratos_pagos_parciales(self, user, mock_geocode):
        inmueble = crear_inmueble(
            titulo="Local San Juan",
            direccion="Av. Siempre Viva 123",
            creado_por=user,
            tipo="local",
            precio=50000,
            habitaciones=3,
        )
        inmueble.tipo_alquiler = Inmueble.TipoAlquiler.POR_HABITACIONES
        inmueble.save(update_fields=["tipo_alquiler"])

        # Contrato 1
        c1 = crear_contrato(
            inmueble=inmueble,
            tipo="alquiler",
            creado_por=user,
            inquilino_nombre="Ana López",
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
            monto=50000,
        )
        assert c1.estado == Contrato.Estado.ACTIVO

        # Contrato 2
        c2 = crear_contrato(
            inmueble=inmueble,
            tipo="alquiler",
            creado_por=user,
            inquilino_nombre="Luis García",
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
            monto=50000,
        )

        # Cuotas
        cuota1 = generar_cuota_mensual(contrato=c1, creado_por=user)
        cuota2 = generar_cuota_mensual(contrato=c2, creado_por=user)

        # Pagos parciales
        from apps.inmuebles.services import actualizar_estado_cuota, aprobar_pago
        pago_p1 = registrar_pago(cuota=cuota1, monto=30000, fecha_pago=date(2026, 1, 10), metodo_pago="transferencia", creado_por=user)
        aprobar_pago(pago_p1)
        actualizar_estado_cuota(cuota1)
        pago_p2 = registrar_pago(cuota=cuota2, monto=20000, fecha_pago=date(2026, 1, 12), metodo_pago="efectivo", creado_por=user)
        aprobar_pago(pago_p2)
        actualizar_estado_cuota(cuota2)

        cuota1.refresh_from_db()
        cuota2.refresh_from_db()
        assert cuota1.estado == Cuota.Estado.PARCIAL
        assert cuota2.estado == Cuota.Estado.PARCIAL


# ---------------------------------------------------------------------------
# Test 4 — Pago rechazado con motivo
# ---------------------------------------------------------------------------
class TestPagoRechazado:
    def test_pago_rechazado(self, user, mock_geocode):
        inmueble = crear_inmueble(
            titulo="Terreno Norte",
            direccion="Av. Siempre Viva 123",
            creado_por=user,
            tipo="terreno",
            precio=40000,
        )
        contrato = crear_contrato(
            inmueble=inmueble,
            tipo="alquiler",
            creado_por=user,
            inquilino_nombre="Pedro Ruiz",
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
            monto=40000,
        )
        cuota = generar_cuota_mensual(contrato=contrato, creado_por=user)
        pago = registrar_pago(
            cuota=cuota,
            monto=40000,
            fecha_pago=date(2026, 1, 15),
            metodo_pago="cheque",
            creado_por=user,
            comprobante="CH-001234",
        )

        rechazado = rechazar_pago(pago, motivo="Cheque sin fondos")
        assert rechazado.estado == Pago.Estado.RECHAZADO
        assert rechazado.motivo_rechazo == "Cheque sin fondos"

        cuota.refresh_from_db()
        assert cuota.estado == Cuota.Estado.PENDIENTE

        # No hay recibo para pagos rechazados
        assert not Recibo.objects.filter(pago=rechazado).exists()


# ---------------------------------------------------------------------------
# Test 5 — Pago parcial + segundo pago = pagado
# ---------------------------------------------------------------------------
class TestPagoParcialMultiples:
    def test_dos_pagos_pagan_cuota(self, user, mock_geocode):
        inmueble = crear_inmueble(
            titulo="Casa Sol",
            direccion="Av. Siempre Viva 123",
            creado_por=user,
            tipo="casa",
            precio=100000,
        )
        contrato = crear_contrato(
            inmueble=inmueble,
            tipo="alquiler",
            creado_por=user,
            inquilino_nombre="Laura Fernández",
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
            monto=100000,
        )
        cuota = generar_cuota_mensual(contrato=contrato, creado_por=user)

        # Primer pago parcial
        pago1 = registrar_pago(
            cuota=cuota, monto=60000, fecha_pago=date(2026, 1, 10),
            metodo_pago="transferencia", creado_por=user,
        )
        aprobar_pago(pago1)
        cuota.refresh_from_db()
        assert cuota.estado == Cuota.Estado.PARCIAL

        # Segundo pago cubre el resto
        pago2 = registrar_pago(
            cuota=cuota, monto=40000, fecha_pago=date(2026, 1, 20),
            metodo_pago="transferencia", creado_por=user,
        )
        aprobar_pago(pago2)
        cuota.refresh_from_db()
        assert cuota.estado == Cuota.Estado.PAGADO
        assert cuota.pagos.count() == 2


# ---------------------------------------------------------------------------
# Test 6 — Múltiples cuotas: pagada, vencida, pendiente
# ---------------------------------------------------------------------------
class TestMultiplesCuotas:
    def test_tres_cuotas_estados(self, user, mock_geocode):
        inmueble = crear_inmueble(
            titulo="Dpto Libertad",
            direccion="Av. Siempre Viva 123",
            creado_por=user,
            tipo="dpto",
            precio=50000,
        )
        contrato = crear_contrato(
            inmueble=inmueble,
            tipo="alquiler",
            creado_por=user,
            inquilino_nombre="Roberto Díaz",
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 3, 31),
            monto=50000,
        )

        # Generar 3 cuotas manualmente (sin depender de lógica de fechas)
        cuota1 = Cuota.objects.create(
            contrato=contrato, numero=1, descripcion="Cuota 1 - Enero 2026",
            fecha_vencimiento=date(2026, 1, 1), monto=50000,
        )
        cuota2 = Cuota.objects.create(
            contrato=contrato, numero=2, descripcion="Cuota 2 - Febrero 2026",
            fecha_vencimiento=date(2026, 2, 1), monto=50000,
        )
        cuota3 = Cuota.objects.create(
            contrato=contrato, numero=3, descripcion="Cuota 3 - Marzo 2026",
            fecha_vencimiento=date(2026, 3, 1), monto=50000,
        )

        # Cuota 1: pagada
        pago1 = registrar_pago(
            cuota=cuota1, monto=50000, fecha_pago=date(2026, 1, 10),
            metodo_pago="transferencia", creado_por=user,
        )
        aprobar_pago(pago1)
        cuota1.refresh_from_db()
        assert cuota1.estado == Cuota.Estado.PAGADO

        # Cuota 2: vencida (forzar estado)
        Cuota.objects.filter(pk=cuota2.pk).update(estado=Cuota.Estado.VENCIDO)
        cuota2.refresh_from_db()
        assert cuota2.estado == Cuota.Estado.VENCIDO

        # Cuota 3: pendiente
        cuota3.refresh_from_db()
        assert cuota3.estado == Cuota.Estado.PENDIENTE

        assert contrato.cuotas.count() == 3


# ---------------------------------------------------------------------------
# Test 7 — Contrato de venta con cuota personalizada
# ---------------------------------------------------------------------------
class TestContratoVenta:
    def test_venta_pago_total(self, user, mock_geocode):
        inmueble = crear_inmueble(
            titulo="Casa Premium",
            direccion="Av. Siempre Viva 123",
            creado_por=user,
            tipo="casa",
            precio=200000,
        )
        contrato = crear_contrato(
            inmueble=inmueble,
            tipo="venta",
            creado_por=user,
            inquilino_nombre="Empresa ABC S.A.",
            fecha_inicio=date(2026, 1, 1),
            monto=200000,
        )
        inmueble.refresh_from_db()
        assert inmueble.estado == Inmueble.Estado.VENDIDO

        # Cuota personalizada
        cuota = crear_cuota_personalizada(
            contrato=contrato,
            monto=200000,
            descripcion="Pago total - Venta Casa Premium",
            fecha_vencimiento=date(2026, 2, 28),
            creado_por=user,
        )
        assert cuota.numero == 1
        assert cuota.monto == Decimal("200000.00")

        pago = registrar_pago(
            cuota=cuota, monto=200000, fecha_pago=date(2026, 1, 20),
            metodo_pago="transferencia", creado_por=user,
        )
        aprobar_pago(pago)
        cuota.refresh_from_db()
        assert cuota.estado == Cuota.Estado.PAGADO
        recibo = Recibo.objects.get(pago=pago)
        assert recibo.codigo.startswith("REC-")


# ---------------------------------------------------------------------------
# Test 8 — Multa por atraso, pago total incluye multa
# ---------------------------------------------------------------------------
class TestMultaAtraso:
    def test_multa_y_pago(self, user, mock_geocode):
        inmueble = crear_inmueble(
            titulo="Dpto Atraso",
            direccion="Av. Siempre Viva 123",
            creado_por=user,
            tipo="dpto",
            precio=70000,
        )
        contrato = crear_contrato(
            inmueble=inmueble,
            tipo="alquiler",
            creado_por=user,
            inquilino_nombre="Sofía Martínez",
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
            monto=70000,
        )
        cuota = generar_cuota_mensual(contrato=contrato, creado_por=user)

        # Forzar vencimiento y aplicar multa del 10%
        Cuota.objects.filter(pk=cuota.pk).update(estado=Cuota.Estado.VENCIDO)
        cuota.refresh_from_db()
        cuota = aplicar_multa(cuota=cuota, monto_fijo=7000, motivo="Atraso 15 días")
        assert cuota.monto_multa == Decimal("7000.00")
        assert cuota.total == Decimal("77000.00")

        # Pago total (monto + multa)
        pago = registrar_pago(
            cuota=cuota, monto=77000, fecha_pago=date(2026, 2, 15),
            metodo_pago="transferencia", creado_por=user,
        )
        aprobar_pago(pago)
        cuota.refresh_from_db()
        assert cuota.estado == Cuota.Estado.PAGADO


# ---------------------------------------------------------------------------
# Test 9 — Renovación de contrato
# ---------------------------------------------------------------------------
class TestRenovacionContrato:
    def test_renovar(self, user, mock_geocode):
        inmueble = crear_inmueble(
            titulo="Casa Renovada",
            direccion="Av. Siempre Viva 123",
            creado_por=user,
            tipo="casa",
            precio=80000,
        )
        contrato_original = crear_contrato(
            inmueble=inmueble,
            tipo="alquiler",
            creado_por=user,
            inquilino_nombre="Juan Pérez",
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
            monto=80000,
        )

        # Pagar 1ra cuota del contrato original
        cuota1 = generar_cuota_mensual(contrato=contrato_original, creado_por=user)
        pago1 = registrar_pago(
            cuota=cuota1, monto=80000, fecha_pago=date(2026, 1, 10),
            metodo_pago="transferencia", creado_por=user,
        )
        aprobar_pago(pago1)

        # Renovar contrato
        nuevo_contrato = renovar_contrato(
            contrato_original,
            fecha_inicio=date(2027, 1, 1),
            fecha_fin=date(2027, 12, 31),
            monto=85000,
        )
        contrato_original.refresh_from_db()
        assert contrato_original.estado == Contrato.Estado.FINALIZADO
        assert contrato_original.fecha_finalizacion == date.today()
        assert nuevo_contrato.estado == Contrato.Estado.ACTIVO
        assert nuevo_contrato.monto == Decimal("85000.00")
        assert nuevo_contrato.inquilino_registrado.nombre == "Juan Pérez"

        # Generar cuota del nuevo contrato
        cuota_nueva = generar_cuota_mensual(contrato=nuevo_contrato, creado_por=user)
        assert cuota_nueva.monto == Decimal("85000.00")


# ---------------------------------------------------------------------------
# Test 10 — Rescisión de contrato, inmueble vuelve a disponible
# ---------------------------------------------------------------------------
class TestRescisionContrato:
    def test_rescision(self, user, mock_geocode):
        inmueble = crear_inmueble(
            titulo="Local Rescindido",
            direccion="Av. Siempre Viva 123",
            creado_por=user,
            tipo="local",
            precio=35000,
        )
        contrato = crear_contrato(
            inmueble=inmueble,
            tipo="alquiler",
            creado_por=user,
            inquilino_nombre="Empresa XYZ",
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
            monto=35000,
        )
        inmueble.refresh_from_db()
        assert inmueble.estado == Inmueble.Estado.ALQUILADO

        # Crear cuota pendiente
        cuota = generar_cuota_mensual(contrato=contrato, creado_por=user)
        assert cuota.estado == Cuota.Estado.PENDIENTE

        # Rescindir contrato
        rescindir_contrato(contrato)
        contrato.refresh_from_db()
        assert contrato.estado == Contrato.Estado.RESCINDIDO
        assert contrato.fecha_finalizacion == date.today()

        # Inmueble vuelve a disponible (no hay otros contratos activos)
        inmueble.refresh_from_db()
        assert inmueble.estado == Inmueble.Estado.DISPONIBLE
