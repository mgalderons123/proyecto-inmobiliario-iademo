import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from apps.inmuebles.models import Contrato, DocumentoContrato, Inmueble, Inquilino, Propietario

User = get_user_model()


@pytest.fixture
def mock_geocode(mocker):
    return mocker.patch(
        "apps.inmuebles.services.geocode_address",
        return_value=(-34.603722, -58.381592, "Av. Siempre Viva 123, Buenos Aires, Argentina"),
    )


@pytest.fixture
def inmueble_data():
    return {
        "titulo": "Casa en la playa",
        "direccion": "Av. Siempre Viva 123, Buenos Aires, Argentina",
        "descripcion": "Hermosa casa frente al mar",
        "precio": 150000.00,
        "tipo": "casa",
        "superficie": 120.50,
        "habitaciones": 3,
        "banos": 2,
        "tipo_alquiler": "completa",
    }


# --- Web Views ---

@pytest.mark.django_db
def test_inmueble_list_requires_login(client):
    response = client.get(reverse("inmuebles:list"))
    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_inmueble_list_authenticated(auth_client, user):
    Inmueble.objects.create(
        titulo="Mi casa", direccion="Calle 1", creado_por=user,
        latitud=0, longitud=0,
    )
    Inmueble.objects.create(
        titulo="Mi dpto", direccion="Calle 2", creado_por=user,
        latitud=0, longitud=0,
    )
    response = auth_client.get(reverse("inmuebles:list"))
    assert response.status_code == 200
    assert b"Mi casa" in response.content
    assert b"Mi dpto" in response.content


@pytest.mark.django_db
def test_inmueble_list_only_own(auth_client, user):
    otro = User.objects.create_user(username="otro", password="pass1234")
    Inmueble.objects.create(
        titulo="De otro", direccion="Calle X", creado_por=otro,
        latitud=0, longitud=0,
    )
    response = auth_client.get(reverse("inmuebles:list"))
    assert b"De otro" not in response.content


@pytest.mark.django_db
def test_inmueble_create_get(auth_client):
    response = auth_client.get(reverse("inmuebles:create"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_inmueble_create_post(auth_client, user, inmueble_data, mock_geocode):
    response = auth_client.post(reverse("inmuebles:create"), inmueble_data)
    assert response.status_code == 302
    inmueble = Inmueble.objects.get(titulo="Casa en la playa")
    assert inmueble.creado_por == user
    assert inmueble.latitud is not None


@pytest.mark.django_db
def test_inmueble_detail_requires_owner(auth_client, user):
    otro = User.objects.create_user(username="otro", password="pass1234")
    inmueble = Inmueble.objects.create(
        titulo="Ajeno", direccion="Calle", creado_por=otro,
        latitud=0, longitud=0,
    )
    response = auth_client.get(reverse("inmuebles:detail", kwargs={"pk": inmueble.pk}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_inmueble_detail_with_empty_foto_does_not_crash(auth_client, user):
    from apps.inmuebles.models import FotoInmueble

    inmueble = Inmueble.objects.create(
        titulo="Con foto vacía", direccion="Calle 2", creado_por=user,
        latitud=0, longitud=0,
    )
    FotoInmueble.objects.create(inmueble=inmueble, imagen="")
    response = auth_client.get(reverse("inmuebles:detail", kwargs={"pk": inmueble.pk}))
    assert response.status_code == 200
    assert "Con foto vacía".encode() in response.content


@pytest.mark.django_db
def test_inmueble_update(auth_client, user, inmueble_data, mock_geocode):
    inmueble = Inmueble.objects.create(
        titulo="Original", direccion="Calle 1", creado_por=user,
        latitud=0, longitud=0,
    )
    response = auth_client.post(
        reverse("inmuebles:update", kwargs={"pk": inmueble.pk}),
        {
            **inmueble_data,
            "titulo": "Actualizado",
            "fotos-TOTAL_FORMS": "3",
            "fotos-INITIAL_FORMS": "0",
            "fotos-MIN_NUM_FORMS": "0",
            "fotos-MAX_NUM_FORMS": "10",
        },
    )
    assert response.status_code == 302
    inmueble.refresh_from_db()
    assert inmueble.titulo == "Actualizado"


@pytest.mark.django_db
def test_inmueble_delete(auth_client, user):
    inmueble = Inmueble.objects.create(
        titulo="Para borrar", direccion="Calle", creado_por=user,
        latitud=0, longitud=0,
    )
    response = auth_client.post(reverse("inmuebles:delete", kwargs={"pk": inmueble.pk}))
    assert response.status_code == 302
    assert not Inmueble.objects.filter(pk=inmueble.pk).exists()


# --- API Views ---

@pytest.mark.django_db
def test_api_inmueble_list_requires_auth(api_client):
    response = api_client.get(reverse("api_inmueble_list_create"))
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_api_inmueble_list_authenticated(jwt_client, user):
    Inmueble.objects.create(
        titulo="API Casa", direccion="Av. 1", creado_por=user,
        latitud=0, longitud=0,
    )
    response = jwt_client.get(reverse("api_inmueble_list_create"))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["titulo"] == "API Casa"


@pytest.mark.django_db
def test_api_inmueble_create(jwt_client, user, inmueble_data, mock_geocode):
    response = jwt_client.post(
        reverse("api_inmueble_list_create"),
        inmueble_data,
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["titulo"] == "Casa en la playa"
    assert "latitud" in response.data
    assert response.data["latitud"] is not None


@pytest.mark.django_db
def test_api_inmueble_detail_owner_only(jwt_client, user):
    otro = User.objects.create_user(username="otro2", password="pass1234")
    inmueble = Inmueble.objects.create(
        titulo="Ajeno", direccion="Calle", creado_por=otro,
        latitud=0, longitud=0,
    )
    response = jwt_client.get(reverse("api_inmueble_detail", kwargs={"pk": inmueble.pk}))
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_api_inmueble_update(jwt_client, user, inmueble_data, mock_geocode):
    inmueble = Inmueble.objects.create(
        titulo="Viejo", direccion="Calle 1", creado_por=user,
        latitud=0, longitud=0,
    )
    response = jwt_client.put(
        reverse("api_inmueble_detail", kwargs={"pk": inmueble.pk}),
        {**inmueble_data, "titulo": "Nuevo título"},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["titulo"] == "Nuevo título"


@pytest.mark.django_db
def test_api_inmueble_delete(jwt_client, user):
    inmueble = Inmueble.objects.create(
        titulo="Borrar", direccion="Calle", creado_por=user,
        latitud=0, longitud=0,
    )
    response = jwt_client.delete(reverse("api_inmueble_detail", kwargs={"pk": inmueble.pk}))
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Inmueble.objects.filter(pk=inmueble.pk).exists()


# --- Disponibles ---

@pytest.mark.django_db
def test_inmuebles_disponibles_show_only_disponibles(auth_client, user):
    d1 = Inmueble.objects.create(titulo="Disp", direccion="Calle 1", creado_por=user, latitud=0, longitud=0, estado=Inmueble.Estado.DISPONIBLE)
    Inmueble.objects.create(titulo="Alquilado", direccion="Calle 2", creado_por=user, latitud=0, longitud=0, estado=Inmueble.Estado.ALQUILADO)
    response = auth_client.get(reverse("inmuebles:disponibles"))
    assert response.status_code == 200
    assert b"Disp" in response.content
    assert b"Alquilado" not in response.content


@pytest.mark.django_db
def test_api_inmuebles_disponibles(jwt_client, user):
    Inmueble.objects.create(titulo="Disp API", direccion="Calle 1", creado_por=user, latitud=0, longitud=0, estado=Inmueble.Estado.DISPONIBLE)
    response = jwt_client.get(reverse("api_inmueble_disponibles"))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["titulo"] == "Disp API"


# --- Contratos Web ---

@pytest.mark.django_db
def test_contrato_list(auth_client, user):
    inmueble = Inmueble.objects.create(titulo="Test", direccion="Calle", creado_por=user, latitud=0, longitud=0)
    Contrato.objects.create(inmueble=inmueble, tipo=Contrato.Tipo.ALQUILER, fecha_inicio="2026-01-01", monto=50000, creado_por=user)
    response = auth_client.get(reverse("inmuebles:contrato_list", kwargs={"inmueble_pk": inmueble.pk}))
    assert response.status_code == 200
    assert b"Alquiler" in response.content


@pytest.mark.django_db
def test_contrato_create_post(auth_client, user, mock_geocode):
    inquilino = Inquilino.objects.create(nombre="Juan Pérez", creado_por=user)
    inmueble = Inmueble.objects.create(titulo="En alquiler", direccion="Calle 1", creado_por=user, latitud=0, longitud=0, estado=Inmueble.Estado.DISPONIBLE)
    response = auth_client.post(
        reverse("inmuebles:contrato_create", kwargs={"inmueble_pk": inmueble.pk}),
        {"tipo": "alquiler", "inquilino_registrado": inquilino.pk, "frecuencia_pago": "mensual", "fecha_inicio": "2026-06-01", "monto": 60000},
    )
    assert response.status_code == 302
    assert Contrato.objects.filter(inmueble=inmueble).exists()
    inmueble.refresh_from_db()
    assert inmueble.estado == Inmueble.Estado.ALQUILADO


@pytest.mark.django_db
def test_contrato_finalizar(auth_client, user, mock_geocode):
    inmueble = Inmueble.objects.create(titulo="Finalizar", direccion="Calle", creado_por=user, latitud=0, longitud=0)
    contrato = Contrato.objects.create(inmueble=inmueble, tipo=Contrato.Tipo.ALQUILER, fecha_inicio="2026-01-01", monto=50000, creado_por=user)
    # actualizar estado del inmueble manualmente
    inmueble.estado = Inmueble.Estado.ALQUILADO
    inmueble.save(update_fields=["estado"])
    response = auth_client.post(reverse("inmuebles:contrato_finalizar", kwargs={"pk": contrato.pk}))
    assert response.status_code == 302
    contrato.refresh_from_db()
    assert contrato.estado == Contrato.Estado.FINALIZADO
    inmueble.refresh_from_db()
    assert inmueble.estado == Inmueble.Estado.DISPONIBLE


# --- Contratos API ---

@pytest.mark.django_db
def test_api_contrato_create(jwt_client, user, mock_geocode):
    inmueble = Inmueble.objects.create(titulo="API Contrato", direccion="Calle", creado_por=user, latitud=0, longitud=0, estado=Inmueble.Estado.DISPONIBLE)
    response = jwt_client.post(
        reverse("api_contrato_list_create"),
        {"inmueble": inmueble.pk, "tipo": "venta", "inquilino_nombre": "Cliente API", "fecha_inicio": "2026-06-01", "monto": 100000},
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["tipo"] == "venta"
    assert response.data["inmueble"] == inmueble.pk


@pytest.mark.django_db
def test_api_contrato_list(jwt_client, user):
    inmueble = Inmueble.objects.create(titulo="Con contrato", direccion="Calle", creado_por=user, latitud=0, longitud=0)
    Contrato.objects.create(inmueble=inmueble, tipo=Contrato.Tipo.ALQUILER, fecha_inicio="2026-01-01", monto=50000, creado_por=user)
    response = jwt_client.get(reverse("api_contrato_list_create"))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) >= 1


# --- Propietarios Web ---

@pytest.mark.django_db
def test_propietario_list_requires_login(client):
    response = client.get(reverse("inmuebles:propietario_list"))
    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_propietario_list_authenticated(auth_client, user):
    Propietario.objects.create(nombre="Juan", creado_por=user)
    Propietario.objects.create(nombre="María", creado_por=user)
    response = auth_client.get(reverse("inmuebles:propietario_list"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Juan" in content
    assert "María" in content


@pytest.mark.django_db
def test_propietario_create_post(auth_client, user):
    response = auth_client.post(
        reverse("inmuebles:propietario_create"),
        {"nombre": "Carlos López", "documento": "12345678", "email": "carlos@example.com"},
    )
    assert response.status_code == 302
    prop = Propietario.objects.get(nombre_busqueda="carlos lopez")
    assert prop.creado_por == user


@pytest.mark.django_db
def test_propietario_detail_shows_inmuebles(auth_client, user):
    prop = Propietario.objects.create(nombre="Ana", creado_por=user)
    Inmueble.objects.create(titulo="Casa de Ana", direccion="Calle 1", creado_por=user, latitud=0, longitud=0, propietario=prop)
    response = auth_client.get(reverse("inmuebles:propietario_detail", kwargs={"pk": prop.pk}))
    assert response.status_code == 200
    assert b"Casa de Ana" in response.content


@pytest.mark.django_db
def test_propietario_delete(auth_client, user):
    prop = Propietario.objects.create(nombre="Eliminar", creado_por=user)
    response = auth_client.post(reverse("inmuebles:propietario_delete", kwargs={"pk": prop.pk}))
    assert response.status_code == 302
    assert not Propietario.objects.filter(pk=prop.pk).exists()


# --- Propietarios API ---

@pytest.mark.django_db
def test_api_propietario_list(jwt_client, user):
    Propietario.objects.create(nombre="API Owner", creado_por=user)
    response = jwt_client.get(reverse("api_propietario_list_create"))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1


@pytest.mark.django_db
def test_api_propietario_create(jwt_client, user):
    response = jwt_client.post(
        reverse("api_propietario_list_create"),
        {"nombre": "Nuevo Owner", "documento": "87654321"},
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["nombre"] == "Nuevo Owner"


@pytest.mark.django_db
def test_api_propietario_update(jwt_client, user):
    prop = Propietario.objects.create(nombre="Viejo", creado_por=user)
    response = jwt_client.put(
        reverse("api_propietario_detail", kwargs={"pk": prop.pk}),
        {"nombre": "Actualizado"},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["nombre"] == "Actualizado"


@pytest.mark.django_db
def test_inmueble_asociado_a_propietario(auth_client, user, mock_geocode):
    prop = Propietario.objects.create(nombre="Titular", creado_por=user)
    response = auth_client.post(
        reverse("inmuebles:create"),
        {"titulo": "Con dueño", "direccion": "Av. Siempre Viva 123, Buenos Aires, Argentina",
         "tipo": "casa", "propietario": prop.pk},
    )
    assert response.status_code == 302
    inmueble = Inmueble.objects.get(titulo="Con dueño")
    assert inmueble.propietario == prop


@pytest.mark.django_db
def test_historial_inmuebles_por_propietario(auth_client, user):
    prop = Propietario.objects.create(nombre="Dueño", creado_por=user)
    i1 = Inmueble.objects.create(titulo="Inm1", direccion="Calle 1", creado_por=user, latitud=0, longitud=0, propietario=prop)
    i2 = Inmueble.objects.create(titulo="Inm2", direccion="Calle 2", creado_por=user, latitud=0, longitud=0, propietario=prop)
    response = auth_client.get(reverse("inmuebles:propietario_detail", kwargs={"pk": prop.pk}))
    assert response.status_code == 200
    assert b"Inm1" in response.content
    assert b"Inm2" in response.content
    assert prop.inmuebles.count() == 2


# --- Inquilinos Web ---

@pytest.mark.django_db
def test_inquilino_list_requires_login(client):
    response = client.get(reverse("inmuebles:inquilino_list"))
    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_inquilino_list_authenticated(auth_client, user):
    Inquilino.objects.create(nombre="Luis", creado_por=user)
    Inquilino.objects.create(nombre="Ana", creado_por=user)
    response = auth_client.get(reverse("inmuebles:inquilino_list"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Luis" in content
    assert "Ana" in content


@pytest.mark.django_db
def test_inquilino_create_post(auth_client, user):
    response = auth_client.post(
        reverse("inmuebles:inquilino_create"),
        {"nombre": "Pedro García", "documento": "87654321", "email": "pedro@example.com"},
    )
    assert response.status_code == 302
    inquilino = Inquilino.objects.get(nombre_busqueda="pedro garcia")
    assert inquilino.creado_por == user


@pytest.mark.django_db
def test_inquilino_detail_shows_contratos(auth_client, user):
    inquilino = Inquilino.objects.create(nombre="Maria", creado_por=user)
    inmueble = Inmueble.objects.create(titulo="Depto", direccion="Calle", creado_por=user, latitud=0, longitud=0)
    Contrato.objects.create(
        inmueble=inmueble, tipo=Contrato.Tipo.ALQUILER, inquilino_registrado=inquilino,
        fecha_inicio="2026-01-01", monto=50000, creado_por=user, estado=Contrato.Estado.ACTIVO,
    )
    response = auth_client.get(reverse("inmuebles:inquilino_detail", kwargs={"pk": inquilino.pk}))
    assert response.status_code == 200
    assert b"Depto" in response.content


@pytest.mark.django_db
def test_inquilino_delete(auth_client, user):
    inquilino = Inquilino.objects.create(nombre="Eliminar", creado_por=user)
    response = auth_client.post(reverse("inmuebles:inquilino_delete", kwargs={"pk": inquilino.pk}))
    assert response.status_code == 302
    assert not Inquilino.objects.filter(pk=inquilino.pk).exists()


# --- Inquilinos API ---

@pytest.mark.django_db
def test_api_inquilino_list(jwt_client, user):
    Inquilino.objects.create(nombre="API Inq", creado_por=user)
    response = jwt_client.get(reverse("api_inquilino_list_create"))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1


@pytest.mark.django_db
def test_api_inquilino_create(jwt_client, user):
    response = jwt_client.post(
        reverse("api_inquilino_list_create"),
        {"nombre": "Nuevo Inquilino", "documento": "12345678"},
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["nombre"] == "Nuevo Inquilino"


@pytest.mark.django_db
def test_api_inquilino_update(jwt_client, user):
    inquilino = Inquilino.objects.create(nombre="Viejo", creado_por=user)
    response = jwt_client.put(
        reverse("api_inquilino_detail", kwargs={"pk": inquilino.pk}),
        {"nombre": "Actualizado"},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["nombre"] == "Actualizado"


@pytest.mark.django_db
def test_api_inquilino_contratos_activos_con_contrato(jwt_client, user, mock_geocode):
    inquilino = Inquilino.objects.create(nombre="Con activo", creado_por=user)
    inmueble = Inmueble.objects.create(titulo="Test", direccion="Calle", creado_por=user, latitud=0, longitud=0)
    Contrato.objects.create(inmueble=inmueble, tipo=Contrato.Tipo.ALQUILER, inquilino_registrado=inquilino, fecha_inicio="2026-01-01", monto=50000, creado_por=user)
    response = jwt_client.get(reverse("api_inquilino_contratos_activos", kwargs={"pk": inquilino.pk}))
    assert response.status_code == status.HTTP_200_OK
    assert response.data["tiene_contratos_activos"] is True
    assert len(response.data["contratos"]) == 1


@pytest.mark.django_db
def test_api_inquilino_contratos_activos_sin_contrato(jwt_client, user):
    inquilino = Inquilino.objects.create(nombre="Sin activo", creado_por=user)
    response = jwt_client.get(reverse("api_inquilino_contratos_activos", kwargs={"pk": inquilino.pk}))
    assert response.status_code == status.HTTP_200_OK
    assert response.data["tiene_contratos_activos"] is False
    assert response.data["contratos"] == []


@pytest.mark.django_db
def test_api_inquilino_contratos_activos_ajeno(jwt_client, user):
    otro = User.objects.create_user(username="otro", password="pass1234")
    inquilino = Inquilino.objects.create(nombre="Ajeno", creado_por=otro)
    response = jwt_client.get(reverse("api_inquilino_contratos_activos", kwargs={"pk": inquilino.pk}))
    assert response.status_code == status.HTTP_404_NOT_FOUND


# --- Contrato con inquilino_registrado ---

@pytest.mark.django_db
def test_contrato_con_inquilino_registrado(auth_client, user, mock_geocode):
    inquilino = Inquilino.objects.create(nombre="Inq Registrado", creado_por=user)
    inmueble = Inmueble.objects.create(
        titulo="Alquiler con inq", direccion="Calle 1", creado_por=user,
        latitud=0, longitud=0, estado=Inmueble.Estado.DISPONIBLE,
    )
    response = auth_client.post(
        reverse("inmuebles:contrato_create", kwargs={"inmueble_pk": inmueble.pk}),
        {"tipo": "alquiler", "inquilino_registrado": inquilino.pk, "frecuencia_pago": "mensual",
         "fecha_inicio": "2026-06-01", "monto": 60000},
    )
    assert response.status_code == 302
    contrato = Contrato.objects.get(inmueble=inmueble)
    assert contrato.inquilino_registrado == inquilino
    assert contrato.inquilino_nombre == ""


# --- Contratos Web (Épica 4) ---

@pytest.mark.django_db
def test_contrato_global_list(auth_client, user):
    inmueble = Inmueble.objects.create(titulo="Global", direccion="Calle", creado_por=user, latitud=0, longitud=0)
    Contrato.objects.create(inmueble=inmueble, tipo=Contrato.Tipo.ALQUILER, fecha_inicio="2026-01-01", monto=50000, creado_por=user)
    response = auth_client.get(reverse("inmuebles:contrato_global_list"))
    assert response.status_code == 200
    assert b"Global" in response.content
    assert b"Alquiler" in response.content


@pytest.mark.django_db
def test_contrato_update(auth_client, user):
    inquilino = Inquilino.objects.create(nombre="Nuevo", creado_por=user)
    inmueble = Inmueble.objects.create(titulo="Edit", direccion="Calle", creado_por=user, latitud=0, longitud=0)
    contrato = Contrato.objects.create(inmueble=inmueble, tipo=Contrato.Tipo.ALQUILER, fecha_inicio="2026-01-01", monto=50000, creado_por=user)
    response = auth_client.post(
        reverse("inmuebles:contrato_update", kwargs={"pk": contrato.pk}),
        {"tipo": "venta", "inquilino_registrado": inquilino.pk, "frecuencia_pago": "mensual", "fecha_inicio": "2026-02-01", "monto": 70000},
    )
    assert response.status_code == 302
    contrato.refresh_from_db()
    assert contrato.tipo == "venta"
    assert contrato.monto == 70000


@pytest.mark.django_db
def test_contrato_renovar(auth_client, user, mock_geocode):
    inmueble = Inmueble.objects.create(titulo="Renovar", direccion="Calle", creado_por=user, latitud=0, longitud=0)
    contrato = Contrato.objects.create(
        inmueble=inmueble, tipo=Contrato.Tipo.ALQUILER, inquilino_nombre="Inq",
        fecha_inicio="2026-01-01", fecha_fin="2026-12-31", monto=50000, creado_por=user,
    )
    inmueble.estado = Inmueble.Estado.ALQUILADO
    inmueble.save(update_fields=["estado"])
    response = auth_client.post(
        reverse("inmuebles:contrato_renovar", kwargs={"pk": contrato.pk}),
        {"fecha_inicio": "2027-01-01", "fecha_fin": "2027-12-31", "monto": 55000},
    )
    assert response.status_code == 302
    contrato.refresh_from_db()
    assert contrato.estado == Contrato.Estado.FINALIZADO
    assert Contrato.objects.filter(inmueble=inmueble, estado=Contrato.Estado.ACTIVO).exists()
    nuevo = Contrato.objects.get(inmueble=inmueble, estado=Contrato.Estado.ACTIVO)
    assert nuevo.monto == 55000
    assert nuevo.inquilino_nombre == "Inq"
    inmueble.refresh_from_db()
    assert inmueble.estado == Inmueble.Estado.ALQUILADO


@pytest.mark.django_db
def test_contrato_rescindir(auth_client, user):
    inmueble = Inmueble.objects.create(titulo="Rescindir", direccion="Calle", creado_por=user, latitud=0, longitud=0)
    contrato = Contrato.objects.create(inmueble=inmueble, tipo=Contrato.Tipo.ALQUILER, fecha_inicio="2026-01-01", monto=50000, creado_por=user)
    inmueble.estado = Inmueble.Estado.ALQUILADO
    inmueble.save(update_fields=["estado"])
    response = auth_client.post(reverse("inmuebles:contrato_rescindir", kwargs={"pk": contrato.pk}))
    assert response.status_code == 302
    contrato.refresh_from_db()
    assert contrato.estado == Contrato.Estado.RESCINDIDO
    assert contrato.fecha_finalizacion is not None
    inmueble.refresh_from_db()
    assert inmueble.estado == Inmueble.Estado.DISPONIBLE


# --- Contratos API (Épica 4) ---

@pytest.mark.django_db
def test_api_contrato_update(jwt_client, user):
    inmueble = Inmueble.objects.create(titulo="API Edit", direccion="Calle", creado_por=user, latitud=0, longitud=0)
    contrato = Contrato.objects.create(inmueble=inmueble, tipo=Contrato.Tipo.ALQUILER, fecha_inicio="2026-01-01", monto=50000, creado_por=user)
    response = jwt_client.put(
        reverse("api_contrato_detail", kwargs={"pk": contrato.pk}),
        {"inmueble": inmueble.pk, "tipo": "venta", "inquilino_nombre": "API Edit", "fecha_inicio": "2026-02-01", "monto": 80000},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["tipo"] == "venta"
    assert response.data["monto"] == "80000.00"


@pytest.mark.django_db
def test_api_contrato_renovar(jwt_client, user):
    inmueble = Inmueble.objects.create(titulo="API Renovar", direccion="Calle", creado_por=user, latitud=0, longitud=0)
    contrato = Contrato.objects.create(
        inmueble=inmueble, tipo=Contrato.Tipo.ALQUILER, inquilino_nombre="Inq",
        fecha_inicio="2026-01-01", fecha_fin="2026-12-31", monto=50000, creado_por=user,
    )
    inmueble.estado = Inmueble.Estado.ALQUILADO
    inmueble.save(update_fields=["estado"])
    response = jwt_client.post(
        reverse("api_contrato_renovar", kwargs={"pk": contrato.pk}),
        {"fecha_inicio": "2027-01-01", "fecha_fin": "2027-12-31", "monto": 60000},
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["monto"] == "60000.00"
    contrato.refresh_from_db()
    assert contrato.estado == Contrato.Estado.FINALIZADO


@pytest.mark.django_db
def test_api_contrato_finalizar(jwt_client, user):
    inmueble = Inmueble.objects.create(titulo="API Finalizar", direccion="Calle", creado_por=user, latitud=0, longitud=0)
    contrato = Contrato.objects.create(inmueble=inmueble, tipo=Contrato.Tipo.ALQUILER, fecha_inicio="2026-01-01", monto=50000, creado_por=user)
    inmueble.estado = Inmueble.Estado.ALQUILADO
    inmueble.save(update_fields=["estado"])
    response = jwt_client.post(reverse("api_contrato_finalizar", kwargs={"pk": contrato.pk}))
    assert response.status_code == status.HTTP_200_OK
    contrato.refresh_from_db()
    assert contrato.estado == Contrato.Estado.FINALIZADO


@pytest.mark.django_db
def test_api_contrato_rescindir(jwt_client, user):
    inmueble = Inmueble.objects.create(titulo="API Rescindir", direccion="Calle", creado_por=user, latitud=0, longitud=0)
    contrato = Contrato.objects.create(inmueble=inmueble, tipo=Contrato.Tipo.ALQUILER, fecha_inicio="2026-01-01", monto=50000, creado_por=user)
    inmueble.estado = Inmueble.Estado.ALQUILADO
    inmueble.save(update_fields=["estado"])
    response = jwt_client.post(reverse("api_contrato_rescindir", kwargs={"pk": contrato.pk}))
    assert response.status_code == status.HTTP_200_OK
    contrato.refresh_from_db()
    assert contrato.estado == Contrato.Estado.RESCINDIDO
    assert contrato.fecha_finalizacion is not None
    inmueble.refresh_from_db()
    assert inmueble.estado == Inmueble.Estado.DISPONIBLE


# --- Autorización de Venta y Documentos ---

@pytest.mark.django_db
def test_contrato_autorizacion_venta_crea_reservado(auth_client, user, mock_geocode):
    inquilino = Inquilino.objects.create(nombre="Propietario", creado_por=user)
    inmueble = Inmueble.objects.create(titulo="Autoriz Venta", direccion="Calle", creado_por=user, latitud=0, longitud=0, estado=Inmueble.Estado.DISPONIBLE)
    response = auth_client.post(
        reverse("inmuebles:contrato_create", kwargs={"inmueble_pk": inmueble.pk}),
        {"tipo": "autorizacion_venta", "inquilino_registrado": inquilino.pk, "frecuencia_pago": "mensual", "fecha_inicio": "2026-06-01", "monto": 100000},
    )
    assert response.status_code == 302
    contrato = Contrato.objects.get(inmueble=inmueble)
    assert contrato.tipo == "autorizacion_venta"
    inmueble.refresh_from_db()
    assert inmueble.estado == Inmueble.Estado.RESERVADO


@pytest.mark.django_db
def test_contrato_autorizacion_venta_finalizar_libera(auth_client, user):
    inmueble = Inmueble.objects.create(titulo="Autoriz Finalizar", direccion="Calle", creado_por=user, latitud=0, longitud=0)
    contrato = Contrato.objects.create(inmueble=inmueble, tipo=Contrato.Tipo.AUTORIZACION_VENTA, fecha_inicio="2026-01-01", monto=50000, creado_por=user)
    inmueble.estado = Inmueble.Estado.RESERVADO
    inmueble.save(update_fields=["estado"])
    response = auth_client.post(reverse("inmuebles:contrato_finalizar", kwargs={"pk": contrato.pk}))
    assert response.status_code == 302
    contrato.refresh_from_db()
    assert contrato.estado == Contrato.Estado.FINALIZADO
    inmueble.refresh_from_db()
    assert inmueble.estado == Inmueble.Estado.DISPONIBLE


@pytest.mark.django_db
def test_descargar_documento(auth_client, user):
    inmueble = Inmueble.objects.create(titulo="Doc Test", direccion="Calle", creado_por=user, latitud=0, longitud=0)
    contrato = Contrato.objects.create(inmueble=inmueble, tipo=Contrato.Tipo.ALQUILER, fecha_inicio="2026-01-01", monto=50000, creado_por=user)
    doc = DocumentoContrato.objects.create(
        contrato=contrato, nombre="test.pdf",
        archivo=b"contenido del pdf", content_type="application/pdf", size=17,
    )
    response = auth_client.get(reverse("inmuebles:descargar_documento", kwargs={"pk": doc.pk}))
    assert response.status_code == 200
    assert response.content == b"contenido del pdf"
    assert response["Content-Type"] == "application/pdf"
    assert "test.pdf" in response["Content-Disposition"]


@pytest.mark.django_db
def test_contrato_global_list_filtro_tipo(auth_client, user):
    inmueble = Inmueble.objects.create(titulo="Multi", direccion="Calle", creado_por=user, latitud=0, longitud=0)
    Contrato.objects.create(inmueble=inmueble, tipo=Contrato.Tipo.ALQUILER, fecha_inicio="2026-01-01", monto=50000, creado_por=user)
    Contrato.objects.create(inmueble=inmueble, tipo=Contrato.Tipo.AUTORIZACION_VENTA, fecha_inicio="2026-01-01", monto=50000, creado_por=user)
    response = auth_client.get(reverse("inmuebles:contrato_global_list") + "?tipo=alquiler")
    assert response.status_code == 200
    assert b"Alquiler" in response.content
    response2 = auth_client.get(reverse("inmuebles:contrato_global_list") + "?tipo=autorizacion_venta")
    assert response2.status_code == 200
    assert b"Autorizaci" in response2.content


@pytest.mark.django_db
def test_api_documento_create(jwt_client, user):
    inmueble = Inmueble.objects.create(titulo="Doc API", direccion="Calle", creado_por=user, latitud=0, longitud=0)
    contrato = Contrato.objects.create(inmueble=inmueble, tipo=Contrato.Tipo.ALQUILER, fecha_inicio="2026-01-01", monto=50000, creado_por=user)
    from django.core.files.uploadedfile import SimpleUploadedFile
    archivo = SimpleUploadedFile("contrato.pdf", b"%PDF-content", content_type="application/pdf")
    response = jwt_client.post(
        reverse("api_documento_create"),
        {"contrato": contrato.pk, "archivo": archivo, "nombre": "Test Doc"},
        format="multipart",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["nombre"] == "Test Doc"
    assert contrato.documentos.count() == 1
    doc = contrato.documentos.first()
    assert doc.content_type == "application/pdf"
    assert doc.size == 12
    assert doc.archivo == b"%PDF-content"


# --- Cobros - Cuotas ---

@pytest.mark.django_db
def test_generar_cuota_mensual(user, mock_geocode):
    from apps.inmuebles.services import crear_inmueble, crear_contrato, generar_cuota_mensual
    from apps.inmuebles.models import Cuota
    inmueble = crear_inmueble(titulo="Test", direccion="Dir 123", creado_por=user)
    contrato = crear_contrato(
        inmueble=inmueble, tipo="alquiler", creado_por=user,
        inquilino_nombre="Juan", fecha_inicio="2026-01-01", fecha_fin="2026-12-31",
        monto=50000,
    )
    cuota = generar_cuota_mensual(contrato=contrato, creado_por=user)
    assert cuota.numero == 1
    assert cuota.monto == 50000
    assert cuota.monto_multa == 0
    assert cuota.estado == Cuota.Estado.PENDIENTE
    assert contrato.cuotas.count() == 1


@pytest.mark.django_db
def test_generar_cuota_mensual_solo_alquiler(user, mock_geocode):
    from apps.inmuebles.services import crear_inmueble, crear_contrato, generar_cuota_mensual, CuotaError
    inmueble = crear_inmueble(titulo="Test", direccion="Dir 123", creado_por=user)
    contrato = crear_contrato(
        inmueble=inmueble, tipo="venta", creado_por=user,
        inquilino_nombre="Juan", fecha_inicio="2026-01-01", monto=100000,
    )
    with pytest.raises(CuotaError):
        generar_cuota_mensual(contrato=contrato, creado_por=user)


@pytest.mark.django_db
def test_crear_cuota_personalizada(user, mock_geocode):
    from apps.inmuebles.services import crear_inmueble, crear_contrato, crear_cuota_personalizada
    from apps.inmuebles.models import Cuota
    inmueble = crear_inmueble(titulo="Test", direccion="Dir 123", creado_por=user)
    contrato = crear_contrato(
        inmueble=inmueble, tipo="venta", creado_por=user,
        inquilino_nombre="Juan", fecha_inicio="2026-01-01", monto=100000,
    )
    cuota = crear_cuota_personalizada(
        contrato=contrato, monto=30000, descripcion="Reserva",
        fecha_vencimiento="2026-02-01", creado_por=user,
    )
    assert cuota.numero == 1
    assert cuota.monto == 30000
    assert cuota.descripcion == "Reserva"


# --- Cobros - Pagos ---

@pytest.mark.django_db
def test_registrar_pago_completo(user, mock_geocode):
    from apps.inmuebles.services import crear_inmueble, crear_contrato, generar_cuota_mensual, registrar_pago
    from apps.inmuebles.models import Cuota, Pago
    inmueble = crear_inmueble(titulo="Test", direccion="Dir 123", creado_por=user)
    contrato = crear_contrato(
        inmueble=inmueble, tipo="alquiler", creado_por=user,
        inquilino_nombre="Juan", fecha_inicio="2026-01-01", fecha_fin="2026-12-31",
        monto=50000,
    )
    cuota = generar_cuota_mensual(contrato=contrato, creado_por=user)
    pago = registrar_pago(cuota=cuota, monto=50000, fecha_pago="2026-01-15", metodo_pago="transferencia", creado_por=user)
    assert pago.monto == 50000
    assert pago.estado == Pago.Estado.PENDIENTE
    cuota.refresh_from_db()
    assert cuota.estado == Cuota.Estado.PENDIENTE


@pytest.mark.django_db
def test_registrar_pago_parcial(user, mock_geocode):
    from apps.inmuebles.services import crear_inmueble, crear_contrato, generar_cuota_mensual, registrar_pago
    from apps.inmuebles.models import Cuota
    inmueble = crear_inmueble(titulo="Test", direccion="Dir 123", creado_por=user)
    contrato = crear_contrato(
        inmueble=inmueble, tipo="alquiler", creado_por=user,
        inquilino_nombre="Juan", fecha_inicio="2026-01-01", fecha_fin="2026-12-31",
        monto=50000,
    )
    cuota = generar_cuota_mensual(contrato=contrato, creado_por=user)
    registrar_pago(cuota=cuota, monto=20000, fecha_pago="2026-01-15", metodo_pago="efectivo", creado_por=user)
    cuota.refresh_from_db()
    assert cuota.estado == Cuota.Estado.PENDIENTE


# --- Cobros - Multas ---

@pytest.mark.django_db
def test_aplicar_multa_monto_fijo(user, mock_geocode):
    from apps.inmuebles.services import crear_inmueble, crear_contrato, generar_cuota_mensual, aplicar_multa
    from apps.inmuebles.models import Cuota
    inmueble = crear_inmueble(titulo="Test", direccion="Dir 123", creado_por=user)
    contrato = crear_contrato(
        inmueble=inmueble, tipo="alquiler", creado_por=user,
        inquilino_nombre="Juan", fecha_inicio="2026-01-01", fecha_fin="2026-12-31",
        monto=50000,
    )
    cuota = generar_cuota_mensual(contrato=contrato, creado_por=user)
    cuota.estado = Cuota.Estado.VENCIDO
    cuota.save()
    aplicar_multa(cuota=cuota, monto_fijo=5000, motivo="Mora")
    cuota.refresh_from_db()
    assert cuota.monto_multa == 5000
    assert cuota.total == 55000


@pytest.mark.django_db
def test_aplicar_multa_porcentaje(user, mock_geocode):
    from apps.inmuebles.services import crear_inmueble, crear_contrato, generar_cuota_mensual, aplicar_multa
    from apps.inmuebles.models import Cuota
    inmueble = crear_inmueble(titulo="Test", direccion="Dir 123", creado_por=user)
    contrato = crear_contrato(
        inmueble=inmueble, tipo="alquiler", creado_por=user,
        inquilino_nombre="Juan", fecha_inicio="2026-01-01", fecha_fin="2026-12-31",
        monto=50000,
    )
    cuota = generar_cuota_mensual(contrato=contrato, creado_por=user)
    cuota.estado = Cuota.Estado.VENCIDO
    cuota.save()
    aplicar_multa(cuota=cuota, porcentaje=10, motivo="Mora 10%")
    cuota.refresh_from_db()
    assert cuota.monto_multa == 5000  # 10% of 50000
    assert cuota.total == 55000
