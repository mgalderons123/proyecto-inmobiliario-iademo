from datetime import date
from decimal import Decimal

import pytest
from django.urls import include, path, reverse

from apps.inmuebles.models import Contrato, Cuota, Inmueble
from PRY_INMOB.urls import urlpatterns as project_urlpatterns


pytestmark = pytest.mark.django_db

urlpatterns = [
    *project_urlpatterns,
    path("_dev/ui/", include(("apps.devtools.urls", "devtools"))),
]


def test_contact_form_uses_accessible_renderer(auth_client):
    response = auth_client.post(
        reverse("inmuebles:inquilino_create"),
        {"nombre": "", "email": "correo-invalido"},
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "form-card--dossier" in content
    assert "data-form-error-summary" in content
    assert 'aria-invalid="true"' in content
    assert 'aria-errormessage="id_nombre_error"' in content
    assert 'href="#id_nombre"' in content


def test_contact_forms_share_the_same_visual_contract(auth_client):
    tenant = auth_client.get(reverse("inmuebles:inquilino_create"))
    owner = auth_client.get(reverse("inmuebles:propietario_create"))

    assert tenant.status_code == owner.status_code == 200
    assert b"form-card--dossier" in tenant.content
    assert b"form-card--dossier" in owner.content
    assert b"Expediente de contacto" in tenant.content
    assert b"Expediente de contacto" in owner.content
    assert b'id="id_nombre_helptext"' in tenant.content
    assert b'aria-describedby="id_nombre_helptext"' in tenant.content


def test_admin_payment_form_supports_file_upload(auth_client, user):
    inmueble = Inmueble.objects.create(
        titulo="Pago UI",
        direccion="Calle 1",
        creado_por=user,
    )
    contrato = Contrato.objects.create(
        inmueble=inmueble,
        tipo=Contrato.Tipo.ALQUILER,
        fecha_inicio=date.today(),
        monto=Decimal("100.00"),
        creado_por=user,
    )
    cuota = Cuota.objects.create(
        contrato=contrato,
        numero=1,
        descripcion="Cuota UI",
        fecha_vencimiento=date.today(),
        monto=Decimal("100.00"),
    )

    response = auth_client.get(reverse("inmuebles:pago_create", kwargs={"cuota_pk": cuota.pk}))

    assert response.status_code == 200
    assert b'enctype="multipart/form-data"' in response.content


@pytest.mark.urls("tests.test_form_ui")
def test_form_catalog_requires_staff(client):
    response = client.get(reverse("devtools:form_catalog"))

    assert response.status_code == 302
    assert response.url.startswith("/admin/login/?next=")


@pytest.mark.urls("tests.test_form_ui")
def test_form_catalog_renders_all_states_for_staff(auth_client, user, settings):
    settings.DEBUG = True
    if "apps.devtools" not in settings.INSTALLED_APPS:
        settings.INSTALLED_APPS = [*settings.INSTALLED_APPS, "apps.devtools"]
    user.is_staff = True
    user.save(update_fields=["is_staff"])

    response = auth_client.get(reverse("devtools:form_catalog"))

    assert response.status_code == 200
    assert b"Estado vac" in response.content
    assert b"data-form-error-summary" in response.content
    assert b'aria-invalid="true"' in response.content
    assert b"Estado completo" in response.content


@pytest.mark.urls("tests.test_form_ui")
def test_form_catalog_returns_404_outside_debug(auth_client, user, settings):
    settings.DEBUG = False
    user.is_staff = True
    user.save(update_fields=["is_staff"])

    response = auth_client.get(reverse("devtools:form_catalog"))

    assert response.status_code == 404
