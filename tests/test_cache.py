from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
@override_settings(PUBLIC_LANDING_CACHE_TIMEOUT=300)
def test_public_landing_reuses_cached_render(client):
    from apps.core import views

    with patch("apps.core.views.render", wraps=views.render) as render_mock:
        first = client.get(reverse("core:home"))
        second = client.get(reverse("core:home"))

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.content == second.content
    assert render_mock.call_count == 1


@pytest.mark.django_db
@override_settings(PUBLIC_LANDING_CACHE_TIMEOUT=300)
def test_public_landing_cache_varies_by_language(client):
    from apps.core import views

    with patch("apps.core.views.render", wraps=views.render) as render_mock:
        client.get(reverse("core:home"), HTTP_ACCEPT_LANGUAGE="es")
        client.get(reverse("core:home"), HTTP_ACCEPT_LANGUAGE="en")
        client.get(reverse("core:home"), HTTP_ACCEPT_LANGUAGE="es")

    assert render_mock.call_count == 2


@pytest.mark.django_db
@override_settings(PUBLIC_LANDING_CACHE_TIMEOUT=300)
def test_public_landing_supports_conditional_requests(client):
    first = client.get(reverse("core:home"))
    second = client.get(reverse("core:home"), HTTP_IF_NONE_MATCH=first["ETag"])

    assert first.status_code == 200
    assert first["Cache-Control"] == "private, no-cache"
    assert second.status_code == 304
    assert second.content == b""
    assert second["ETag"] == first["ETag"]


@pytest.mark.django_db
@override_settings(PUBLIC_LANDING_CACHE_TIMEOUT=300)
def test_authenticated_home_never_uses_public_landing(auth_client):
    response = auth_client.get(reverse("core:home"))

    assert response.status_code == 200
    assert b"Bienvenido" in response.content
    assert "Gestioná tu portfolio inmobiliario".encode() not in response.content


@pytest.mark.django_db
@override_settings(PUBLIC_LANDING_CACHE_TIMEOUT=300)
def test_public_landing_survives_cache_failure(client):
    with (
        patch("apps.core.views.cache.get", side_effect=ConnectionError),
        patch("apps.core.views.cache.set", side_effect=ConnectionError),
    ):
        response = client.get(reverse("core:home"))

    assert response.status_code == 200
    assert "Gestioná tu portfolio inmobiliario".encode() in response.content
