import pytest
from datetime import date

pytestmark = pytest.mark.django_db


@pytest.fixture
def _mock_geocode(mocker):
    return mocker.patch(
        "apps.inmuebles.services.geocode_address",
        return_value=(-34.603722, -58.381592, "Av. Siempre Viva 123, Buenos Aires, Argentina"),
    )


class TestIngresosMensuales:
    def test_sin_pagos(self, user):
        from apps.inmuebles.services_reportes import ingresos_mensuales
        result = ingresos_mensuales(user, date(2026, 1, 1), date(2026, 12, 31))
        assert result == []

    def test_con_pagos(self, user, _mock_geocode):
        from apps.inmuebles.services import crear_inmueble, crear_contrato, generar_cuota_mensual, registrar_pago, aprobar_pago
        from apps.inmuebles.services_reportes import ingresos_mensuales
        inmueble = crear_inmueble(titulo="Test", direccion="Dir 123", creado_por=user)
        contrato = crear_contrato(
            inmueble=inmueble, tipo="alquiler", creado_por=user,
            inquilino_nombre="Juan", fecha_inicio="2026-01-01", fecha_fin="2026-12-31",
            monto=50000,
        )
        cuota = generar_cuota_mensual(contrato=contrato, creado_por=user)
        pago = registrar_pago(cuota=cuota, monto=50000, fecha_pago="2026-01-15", metodo_pago="transferencia", creado_por=user)
        aprobar_pago(pago)
        result = ingresos_mensuales(user, date(2026, 1, 1), date(2026, 12, 31))
        assert len(result) == 1
        assert result[0]["mes"] == 1
        assert result[0]["anio"] == 2026
        assert result[0]["total"] == 50000.0
        assert result[0]["cantidad"] == 1

    def test_filtro_rango(self, user, _mock_geocode):
        from apps.inmuebles.services import crear_inmueble, crear_contrato, generar_cuota_mensual, registrar_pago
        from apps.inmuebles.services_reportes import ingresos_mensuales
        inmueble = crear_inmueble(titulo="Test", direccion="Dir 123", creado_por=user)
        contrato = crear_contrato(
            inmueble=inmueble, tipo="alquiler", creado_por=user,
            inquilino_nombre="Juan", fecha_inicio="2026-01-01", fecha_fin="2026-12-31",
            monto=50000,
        )
        cuota = generar_cuota_mensual(contrato=contrato, creado_por=user)
        registrar_pago(cuota=cuota, monto=50000, fecha_pago="2026-01-15", metodo_pago="transferencia", creado_por=user)
        result = ingresos_mensuales(user, date(2026, 2, 1), date(2026, 12, 31))
        assert result == []

    def test_solo_usuario_actual(self, user, _mock_geocode):
        from apps.inmuebles.services import crear_inmueble, crear_contrato, generar_cuota_mensual, registrar_pago
        from apps.inmuebles.services_reportes import ingresos_mensuales
        from django.contrib.auth import get_user_model
        otro = get_user_model().objects.create_user(username="otro", password="p")
        inmueble = crear_inmueble(titulo="Test", direccion="Dir 123", creado_por=otro)
        contrato = crear_contrato(
            inmueble=inmueble, tipo="alquiler", creado_por=otro,
            inquilino_nombre="Juan", fecha_inicio="2026-01-01", fecha_fin="2026-12-31",
            monto=50000,
        )
        cuota = generar_cuota_mensual(contrato=contrato, creado_por=otro)
        registrar_pago(cuota=cuota, monto=50000, fecha_pago="2026-01-15", metodo_pago="transferencia", creado_por=otro)
        result = ingresos_mensuales(user, date(2026, 1, 1), date(2026, 12, 31))
        assert result == []


class TestCarteraVencida:
    def test_sin_vencidos(self, user):
        from apps.inmuebles.services_reportes import cartera_vencida
        result = cartera_vencida(user, date(2020, 1, 1), date(2030, 12, 31))
        assert result == []

    def test_con_vencidos(self, user, _mock_geocode):
        from apps.inmuebles.services import crear_inmueble, crear_contrato, generar_cuota_mensual
        from apps.inmuebles.models import Cuota
        from apps.inmuebles.services_reportes import cartera_vencida
        inmueble = crear_inmueble(titulo="Test", direccion="Dir 123", creado_por=user)
        contrato = crear_contrato(
            inmueble=inmueble, tipo="alquiler", creado_por=user,
            inquilino_nombre="Juan", fecha_inicio="2026-01-01", fecha_fin="2026-12-31",
            monto=50000,
        )
        cuota = generar_cuota_mensual(contrato=contrato, creado_por=user)
        Cuota.objects.filter(pk=cuota.pk).update(estado=Cuota.Estado.VENCIDO)
        result = cartera_vencida(user, date(2020, 1, 1), date(2030, 12, 31))
        assert len(result) == 1
        assert result[0].pk == cuota.pk

    def test_excluye_pagadas(self, user, _mock_geocode):
        from apps.inmuebles.services import crear_inmueble, crear_contrato, generar_cuota_mensual, registrar_pago
        from apps.inmuebles.models import Cuota
        from apps.inmuebles.services_reportes import cartera_vencida
        inmueble = crear_inmueble(titulo="Test", direccion="Dir 123", creado_por=user)
        contrato = crear_contrato(
            inmueble=inmueble, tipo="alquiler", creado_por=user,
            inquilino_nombre="Juan", fecha_inicio="2026-01-01", fecha_fin="2026-12-31",
            monto=50000,
        )
        cuota = generar_cuota_mensual(contrato=contrato, creado_por=user)
        pago = registrar_pago(cuota=cuota, monto=50000, fecha_pago="2026-01-15", metodo_pago="transferencia", creado_por=user)
        from apps.inmuebles.services import aprobar_pago
        aprobar_pago(pago)
        cuota.refresh_from_db()
        assert cuota.estado == Cuota.Estado.PAGADO
        result = cartera_vencida(user, date(2020, 1, 1), date(2030, 12, 31))
        assert result == []

    def test_solo_usuario_actual(self, user, _mock_geocode):
        from apps.inmuebles.services import crear_inmueble, crear_contrato, generar_cuota_mensual
        from apps.inmuebles.models import Cuota
        from apps.inmuebles.services_reportes import cartera_vencida
        from django.contrib.auth import get_user_model
        otro = get_user_model().objects.create_user(username="otro2", password="p")
        inmueble = crear_inmueble(titulo="Test", direccion="Dir 123", creado_por=otro)
        contrato = crear_contrato(
            inmueble=inmueble, tipo="alquiler", creado_por=otro,
            inquilino_nombre="Juan", fecha_inicio="2026-01-01", fecha_fin="2026-12-31",
            monto=50000,
        )
        cuota = generar_cuota_mensual(contrato=contrato, creado_por=otro)
        Cuota.objects.filter(pk=cuota.pk).update(estado=Cuota.Estado.VENCIDO)
        result = cartera_vencida(user, date(2020, 1, 1), date(2030, 12, 31))
        assert result == []


class TestResumenCarteraVencida:
    def test_resumen(self, user, _mock_geocode):
        from apps.inmuebles.services import crear_inmueble, crear_contrato, generar_cuota_mensual
        from apps.inmuebles.models import Cuota
        from apps.inmuebles.services_reportes import cartera_vencida, resumen_cartera_vencida
        inmueble = crear_inmueble(titulo="Test", direccion="Dir 123", creado_por=user)
        contrato = crear_contrato(
            inmueble=inmueble, tipo="alquiler", creado_por=user,
            inquilino_nombre="Juan", fecha_inicio="2026-01-01", fecha_fin="2026-12-31",
            monto=50000,
        )
        cuota = generar_cuota_mensual(contrato=contrato, creado_por=user)
        Cuota.objects.filter(pk=cuota.pk).update(estado=Cuota.Estado.VENCIDO)
        cuotas = cartera_vencida(user, date(2020, 1, 1), date(2030, 12, 31))
        resumen = resumen_cartera_vencida(cuotas)
        assert resumen["cantidad_cuotas"] == 1
        assert resumen["cantidad_contratos"] == 1
        assert resumen["total_adeudado"] > 0

    def test_resumen_sin_datos(self, user):
        from apps.inmuebles.services_reportes import resumen_cartera_vencida
        resumen = resumen_cartera_vencida([])
        assert resumen["cantidad_cuotas"] == 0
        assert resumen["total_adeudado"] == 0


class TestDashboardViews:
    def test_dashboard_requires_login(self, client):
        from django.urls import reverse
        response = client.get(reverse("inmuebles:dashboard"))
        assert response.status_code == 302

    def test_dashboard_authenticated(self, auth_client):
        from django.urls import reverse
        response = auth_client.get(reverse("inmuebles:dashboard"))
        assert response.status_code == 200
        assert b"Dashboard" in response.content

    def test_dashboard_con_datos(self, auth_client, user, _mock_geocode):
        from django.urls import reverse
        from apps.inmuebles.services import crear_inmueble, crear_contrato, generar_cuota_mensual, registrar_pago
        from apps.inmuebles.models import Cuota
        inmueble = crear_inmueble(titulo="Test", direccion="Dir 123", creado_por=user)
        contrato = crear_contrato(
            inmueble=inmueble, tipo="alquiler", creado_por=user,
            inquilino_nombre="Juan", fecha_inicio="2026-01-01", fecha_fin="2026-12-31",
            monto=50000,
        )
        cuota = generar_cuota_mensual(contrato=contrato, creado_por=user)
        registrar_pago(cuota=cuota, monto=50000, fecha_pago="2026-01-15", metodo_pago="transferencia", creado_por=user)
        Cuota.objects.filter(pk=cuota.pk).update(estado=Cuota.Estado.VENCIDO)
        response = auth_client.get(reverse("inmuebles:dashboard"))
        assert response.status_code == 200
        assert b"Total Adeudado" in response.content

    def test_dashboard_pdf_authenticated(self, auth_client):
        from django.urls import reverse
        response = auth_client.get(reverse("inmuebles:dashboard_pdf"))
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
