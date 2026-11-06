import re

import pytest
from django.urls import reverse

from apps.users.models import UserTheme


def html_theme(content):
    match = re.search(rb'<html lang="es" data-theme="([a-z_]+)"', content)
    assert match, "no se encontró <html data-theme=...> en el HTML"
    return match.group(1).decode()


@pytest.mark.django_db
def test_profile_shows_theme_section(auth_client):
    response = auth_client.get(reverse("core:profile"))
    assert response.status_code == 200
    assert "Apariencia de la aplicación".encode() in response.content
    assert b'name="theme"' in response.content
    assert b'name="custom_primary"' in response.content


@pytest.mark.django_db
def test_anonymous_uses_default_theme(client):
    response = client.get(reverse("login"))
    assert response.status_code == 200
    assert html_theme(response.content) == "default"


@pytest.mark.django_db
def test_save_preset_theme_applies(auth_client, user):
    response = auth_client.post(reverse("core:profile"), {"theme": "navy"})
    assert response.status_code == 302
    theme = UserTheme.objects.get(user=user)
    assert theme.theme == "navy"

    home = auth_client.get(reverse("core:home"))
    assert html_theme(home.content) == "navy"


@pytest.mark.django_db
def test_save_custom_theme(auth_client, user):
    payload = {
        "theme": "custom",
        "custom_primary": "#0F766E",
        "custom_primary_hover": "#115E59",
        "custom_accent": "#0369A1",
        "custom_sidebar": "#134E4A",
        "custom_bg": "#F0FDFA",
        "custom_border": "#D8EDE8",
        "custom_text": "#134E4A",
    }
    response = auth_client.post(reverse("core:profile"), payload)
    assert response.status_code == 302
    theme = UserTheme.objects.get(user=user)
    assert theme.theme == "custom"
    assert theme.custom_primary == "#0F766E"

    home = auth_client.get(reverse("core:home"))
    assert html_theme(home.content) == "custom"
    assert b"--color-primary:#0F766E" in home.content


@pytest.mark.django_db
def test_invalid_custom_hex_is_rejected(auth_client, user):
    payload = {
        "theme": "custom",
        "custom_primary": "notacolor",
        "custom_primary_hover": "#115E59",
        "custom_accent": "#0369A1",
        "custom_sidebar": "#134E4A",
        "custom_bg": "#F0FDFA",
        "custom_border": "#D8EDE8",
        "custom_text": "#134E4A",
    }
    response = auth_client.post(reverse("core:profile"), payload)
    assert response.status_code == 302
    theme = UserTheme.objects.get(user=user)
    assert theme.theme == "default"
    assert theme.custom_primary == ""


@pytest.mark.django_db
def test_invalid_theme_value_is_rejected(auth_client, user):
    response = auth_client.post(reverse("core:profile"), {"theme": "hotdog"})
    assert response.status_code == 302
    theme = UserTheme.objects.get(user=user)
    assert theme.theme == "default"


@pytest.mark.django_db
def test_reset_to_default(auth_client, user):
    UserTheme.objects.update_or_create(user=user, defaults={"theme": "violet"})
    response = auth_client.post(reverse("core:profile"), {"theme": "default"})
    assert response.status_code == 302
    theme = UserTheme.objects.get(user=user)
    assert theme.theme == "default"
    home = auth_client.get(reverse("core:home"))
    assert html_theme(home.content) == "default"


@pytest.mark.django_db
def test_theme_does_not_leak_between_users(client, user):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    other = User.objects.create_user(
        username="other", email="other@example.com", password="pass12345"
    )
    UserTheme.objects.create(user=user, theme="navy")

    client.login(username="other", password="pass12345")
    home = client.get(reverse("core:home"))
    assert html_theme(home.content) == "default"


@pytest.mark.django_db
def test_form_page_uses_zoho_frame_with_active_theme(auth_client, user):
    UserTheme.objects.update_or_create(user=user, defaults={"theme": "violet"})
    membership = user.membresias_cuenta.get()
    membership.cuenta.theme = "violet"
    membership.cuenta.save(update_fields=["theme"])
    response = auth_client.get(reverse("inmuebles:create"))
    assert response.status_code == 200
    assert b'class="form-card"' in response.content
    assert b'class="form-card__header"' in response.content
    assert html_theme(response.content) == "violet"
