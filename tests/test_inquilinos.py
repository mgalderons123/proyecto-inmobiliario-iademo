import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from decimal import Decimal
from datetime import date, timedelta

from apps.inmuebles.models import Contrato, Cuota, Inmueble, Inquilino, Pago

User = get_user_model()


@pytest.fixture
def inquilino_user(db):
    owner = User.objects.create_user(
        username="owner", email="owner@example.com", password="pass1234",
    )
    inquilino = Inquilino.objects.create(
        nombre="Juan Inquilino",
        email="juan@test.com",
        creado_por=owner,
    )
    user = User.objects.create_user(
        username="inquilino",
        email="inquilino@test.com",
        password="pass1234",
        is_active=True,
    )
    inquilino.user = user
    inquilino.save()
    return user, inquilino, owner


@pytest.fixture
def mock_geocode(mocker):
    return mocker.patch(
        "apps.inmuebles.services.geocode_address",
        return_value=(-34.603722, -58.381592, "Av. Libertador 100, Buenos Aires, Argentina"),
    )


@pytest.fixture
def contrato_activo(inquilino_user, mock_geocode):
    user, inquilino, owner = inquilino_user
    inmueble = Inmueble.objects.create(
        titulo="Depto Centro",
        direccion="Av. Libertador 100",
        creado_por=owner,
        latitud=0, longitud=0,
    )
    contrato = Contrato.objects.create(
        inmueble=inmueble,
        tipo=Contrato.Tipo.ALQUILER,
        estado=Contrato.Estado.ACTIVO,
        inquilino_registrado=inquilino,
        creado_por=owner,
        fecha_inicio=date.today(),
        fecha_fin=date.today() + timedelta(days=365),
        monto=Decimal("50000.00"),
    )
    return contrato


def _login(user):
    c = __import__("django.test", fromlist=["Client"]).Client()
    c.login(username=user.username, password="pass1234")
    return c


# --- Portal requires login ---

@pytest.mark.django_db
def test_portal_requires_login(client):
    response = client.get(reverse("inmuebles:portal"))
    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_portal_requires_inquilino_user(auth_client):
    response = auth_client.get(reverse("inmuebles:portal"))
    assert response.status_code == 302


# --- Portal dashboard ---

@pytest.mark.django_db
def test_portal_renders(inquilino_user, contrato_activo):
    user, inquilino, owner = inquilino_user
    c = _login(user)
    response = c.get(reverse("inmuebles:portal"))
    assert response.status_code == 200
    assert "Juan Inquilino".encode() in response.content
    assert b"Mi Portal"


@pytest.mark.django_db
def test_portal_only_own_data(inquilino_user, contrato_activo):
    user, inquilino, owner = inquilino_user
    owner_user = User.objects.create_user(
        username="other", email="other@example.com", password="pass1234",
    )
    Inquilino.objects.create(nombre="Otro Inquilino", email="otro@test.com", creado_por=owner)
    c = _login(owner_user)
    response = c.get(reverse("inmuebles:portal"))
    assert response.status_code == 302


# --- Portal contratos ---

@pytest.mark.django_db
def test_portal_contratos_renders(inquilino_user, contrato_activo):
    user, inquilino, owner = inquilino_user
    c = _login(user)
    response = c.get(reverse("inmuebles:portal_contratos"))
    assert response.status_code == 200
    assert b"Depto Centro"


@pytest.mark.django_db
def test_portal_contratos_both_fks(inquilino_user, mock_geocode):
    user, inquilino, owner = inquilino_user
    inmueble = Inmueble.objects.create(
        titulo="Casa Playa",
        direccion="Costa 50",
        creado_por=owner,
        latitud=0, longitud=0,
    )
    Contrato.objects.create(
        inmueble=inmueble,
        tipo=Contrato.Tipo.ALQUILER,
        estado=Contrato.Estado.ACTIVO,
        inquilino=user,
        inquilino_registrado=None,
        creado_por=owner,
        fecha_inicio=date.today(),
        fecha_fin=date.today() + timedelta(days=365),
        monto=Decimal("80000.00"),
    )
    c = _login(user)
    response = c.get(reverse("inmuebles:portal_contratos"))
    assert response.status_code == 200
    assert b"Casa Playa"
    assert b"Depto Centro"


# --- Portal cuotas ---

@pytest.mark.django_db
def test_portal_cuotas_renders(inquilino_user, contrato_activo):
    user, inquilino, owner = inquilino_user
    Cuota.objects.create(
        contrato=contrato_activo,
        numero=1,
        fecha_vencimiento=date.today(),
        monto=Decimal("50000.00"),
    )
    c = _login(user)
    response = c.get(reverse("inmuebles:portal_cuotas", kwargs={"contrato_pk": contrato_activo.pk}))
    assert response.status_code == 200
    assert b"50000.00"


@pytest.mark.django_db
def test_portal_cuotas_not_other_contrato(inquilino_user, contrato_activo):
    user, inquilino, owner = inquilino_user
    owner2 = User.objects.create_user(username="owner2", email="o2@e.com", password="pass1234")
    inmueble2 = Inmueble.objects.create(
        titulo="Otro Depto", direccion="Calle 2", creado_por=owner2, latitud=0, longitud=0,
    )
    otro = Contrato.objects.create(
        inmueble=inmueble2, tipo=Contrato.Tipo.ALQUILER, estado=Contrato.Estado.ACTIVO,
        creado_por=owner2,
        fecha_inicio=date.today(), fecha_fin=date.today() + timedelta(days=365),
        monto=Decimal("40000.00"),
    )
    c = _login(user)
    response = c.get(reverse("inmuebles:portal_cuotas", kwargs={"contrato_pk": otro.pk}))
    assert response.status_code == 404


# --- Portal pago subir ---

@pytest.mark.django_db
def test_portal_pago_subir_renders(inquilino_user, contrato_activo):
    user, inquilino, owner = inquilino_user
    cuota = Cuota.objects.create(
        contrato=contrato_activo, numero=1,
        fecha_vencimiento=date.today(), monto=Decimal("50000.00"),
    )
    c = _login(user)
    response = c.get(reverse("inmuebles:portal_pago_subir", kwargs={"cuota_pk": cuota.pk}))
    assert response.status_code == 200
    assert b"Subir Comprobante"


@pytest.mark.django_db
def test_portal_pago_subir_exitoso(inquilino_user, contrato_activo):
    user, inquilino, owner = inquilino_user
    cuota = Cuota.objects.create(
        contrato=contrato_activo, numero=1,
        fecha_vencimiento=date.today(), monto=Decimal("50000.00"),
    )
    c = _login(user)
    response = c.post(
        reverse("inmuebles:portal_pago_subir", kwargs={"cuota_pk": cuota.pk}),
        {
            "monto": "50000.00",
            "fecha_pago": date.today().isoformat(),
            "metodo_pago": "transferencia",
            "observaciones": "Pago mensual",
        },
    )
    assert response.status_code == 302
    assert Pago.objects.filter(cuota=cuota).exists()


# --- Portal pago detalle ---

@pytest.mark.django_db
def test_portal_pago_detalle_renders(inquilino_user, contrato_activo):
    user, inquilino, owner = inquilino_user
    cuota = Cuota.objects.create(
        contrato=contrato_activo, numero=1,
        fecha_vencimiento=date.today(), monto=Decimal("50000.00"),
    )
    pago = Pago.objects.create(
        cuota=cuota, monto=Decimal("50000.00"), fecha_pago=date.today(),
        metodo_pago="efectivo", creado_por=user,
    )
    c = _login(user)
    response = c.get(reverse("inmuebles:portal_pago_detalle", kwargs={"pk": pago.pk}))
    assert response.status_code == 200
    assert b"50000.00"


# --- Bloqueo de registro ---

@pytest.mark.django_db
def test_register_blocked_for_linked_inquilino_email(client, inquilino_user):
    user, inquilino, owner = inquilino_user
    response = client.post(
        reverse("core:register"),
        {
            "username": "nuevo usuario",
            "email": "juan@test.com",
            "password1": "newpass1234",
            "password2": "newpass1234",
        },
    )
    assert response.status_code == 200
    assert not User.objects.filter(username="nuevo usuario").exists()


@pytest.mark.django_db
def test_register_allowed_for_unlinked_inquilino_email(client):
    owner = User.objects.create_user(username="owner3", email="o3@e.com", password="pass1234")
    inquilino = Inquilino.objects.create(
        nombre="Sin Vinculo", email="libre@test.com", creado_por=owner,
    )
    assert inquilino.user is None
    response = client.post(
        reverse("core:register"),
        {
            "username": "libre_user",
            "email": "libre@test.com",
            "password1": "newpass1234",
            "password2": "newpass1234",
        },
    )
    assert response.status_code == 302
    assert User.objects.filter(username="libre_user").exists()


# --- Admin vinculación/desvinculación ---

@pytest.mark.django_db
def test_inquilino_create_user(client, mock_geocode):
    staff = User.objects.create_user(username="staff1", email="s1@e.com", password="pass1234", is_staff=True)
    inquilino = Inquilino.objects.create(
        nombre="Test Create", email="create@test.com", creado_por=staff,
    )
    client.login(username=staff.username, password="pass1234")
    response = client.post(
        reverse("inmuebles:inquilino_create_user", kwargs={"pk": inquilino.pk}),
    )
    assert response.status_code == 302
    inquilino.refresh_from_db()
    assert inquilino.user is not None
    assert inquilino.user.email == "create@test.com"
    assert inquilino.user.is_active is True
    assert inquilino.user.groups.filter(name="Inquilino").exists()


@pytest.mark.django_db
def test_inquilino_unlink_user(client, mock_geocode):
    staff = User.objects.create_user(username="staff2", email="s2@e.com", password="pass1234", is_staff=True)
    inq_user = User.objects.create_user(username="inq_u", email="inq@t.com", password="pass1234")
    inquilino = Inquilino.objects.create(
        nombre="Test Unlink", email="unl@t.com", creado_por=staff, user=inq_user,
    )
    client.login(username=staff.username, password="pass1234")
    response = client.post(
        reverse("inmuebles:inquilino_unlink_user", kwargs={"pk": inquilino.pk}),
    )
    assert response.status_code == 302
    inquilino.refresh_from_db()
    assert inquilino.user is None


@pytest.mark.django_db
def test_inquilino_detail_shows_link_section(client, mock_geocode):
    staff = User.objects.create_user(username="staff3", email="s3@e.com", password="pass1234", is_staff=True)
    inquilino = Inquilino.objects.create(
        nombre="Link Section", email="ls@t.com", creado_por=staff,
    )
    client.login(username=staff.username, password="pass1234")
    response = client.get(reverse("inmuebles:inquilino_detail", kwargs={"pk": inquilino.pk}))
    assert response.status_code == 200
    assert b"Crear usuario y vincular"


@pytest.mark.django_db
def test_inquilino_detail_shows_linked_user(client, mock_geocode):
    staff = User.objects.create_user(username="staff4", email="s4@e.com", password="pass1234", is_staff=True)
    inq_user = User.objects.create_user(username="linked_u", email="lu@t.com", password="pass1234")
    inquilino = Inquilino.objects.create(
        nombre="Linked", email="lk@t.com", creado_por=staff, user=inq_user,
    )
    client.login(username=staff.username, password="pass1234")
    response = client.get(reverse("inmuebles:inquilino_detail", kwargs={"pk": inquilino.pk}))
    assert response.status_code == 200
    assert b"linked_u"
    assert b"Desvincular usuario"
