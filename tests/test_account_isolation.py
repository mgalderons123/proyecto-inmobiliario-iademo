import pytest
from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.inmuebles.models import Contrato, Cuota, Inmueble, Pago, Propietario
from apps.users.models import Cuenta, MembresiaCuenta


User = get_user_model()


@pytest.fixture
def isolated_accounts(user):
    account_a = user.membresias_cuenta.get().cuenta
    other = User.objects.create_user(username="other-admin", password="testpass123")
    account_b = Cuenta.objects.create(nombre="Cuenta B")
    MembresiaCuenta.objects.create(
        cuenta=account_b,
        user=other,
        rol=MembresiaCuenta.Roles.PROPIETARIO,
    )
    inmueble_a = Inmueble.objects.create(
        cuenta=account_a,
        titulo="Visible A",
        direccion="Calle A",
        creado_por=user,
    )
    inmueble_b = Inmueble.objects.create(
        cuenta=account_b,
        titulo="Oculto B",
        direccion="Calle B",
        creado_por=other,
    )
    propietario_b = Propietario.objects.create(
        cuenta=account_b,
        nombre="Propietario B",
        creado_por=other,
    )
    return account_a, account_b, inmueble_a, inmueble_b, propietario_b


@pytest.mark.django_db
def test_api_list_only_returns_active_account(jwt_client, isolated_accounts):
    _, _, inmueble_a, _, _ = isolated_accounts

    response = jwt_client.get("/api/v1/inmuebles/")

    assert response.status_code == 200
    assert [item["id"] for item in response.data] == [inmueble_a.id]


@pytest.mark.django_db
def test_api_foreign_account_object_returns_404(jwt_client, isolated_accounts):
    _, _, _, inmueble_b, _ = isolated_accounts

    response = jwt_client.get(f"/api/v1/inmuebles/{inmueble_b.pk}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_api_rejects_foreign_relation(jwt_client, isolated_accounts):
    _, _, _, _, propietario_b = isolated_accounts

    response = jwt_client.post(
        "/api/v1/inmuebles/",
        {
            "titulo": "Intento cruzado",
            "direccion": "Calle C",
            "tipo": Inmueble.Tipo.CASA,
            "propietario": propietario_b.pk,
        },
        format="json",
    )

    assert response.status_code == 400
    assert "propietario" in response.data


@pytest.mark.django_db
def test_api_rejects_unrelated_account_header(user, isolated_accounts):
    _, account_b, _, _, _ = isolated_accounts
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_ACCOUNT_ID=str(account_b.pk),
    )

    response = client.get("/api/v1/inmuebles/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_private_receipt_download_does_not_cross_accounts(auth_client, isolated_accounts):
    _, _, _, inmueble_b, _ = isolated_accounts
    contrato = Contrato.objects.create(
        inmueble=inmueble_b,
        tipo=Contrato.Tipo.ALQUILER,
        fecha_inicio=date.today(),
        monto=Decimal("100.00"),
        creado_por=inmueble_b.creado_por,
    )
    cuota = Cuota.objects.create(
        contrato=contrato,
        numero=1,
        fecha_vencimiento=date.today(),
        monto=Decimal("100.00"),
    )
    pago = Pago.objects.create(
        cuota=cuota,
        monto=Decimal("100.00"),
        fecha_pago=date.today(),
        archivo_comprobante=SimpleUploadedFile(
            "comprobante.pdf", b"%PDF-private", content_type="application/pdf"
        ),
    )

    response = auth_client.get(f"/inmuebles/mi-portal/pagos/{pago.pk}/comprobante/")

    assert response.status_code == 404
