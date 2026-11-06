import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

User = get_user_model()


@pytest.mark.django_db
def test_obtain_token_success(api_client, user):
    response = api_client.post(
        reverse("api:token_obtain_pair"),
        {"username": "testuser", "password": "testpass123"},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" in response.data


@pytest.mark.django_db
def test_obtain_token_invalid_credentials(api_client, user):
    response = api_client.post(
        reverse("api:token_obtain_pair"),
        {"username": "testuser", "password": "wrong"},
        format="json",
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_me_requires_auth(api_client):
    response = api_client.get(reverse("api:me"))
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_me_authenticated(jwt_client, user):
    response = jwt_client.get(reverse("api:me"))
    assert response.status_code == status.HTTP_200_OK
    assert response.data["username"] == user.username
    assert response.data["email"] == user.email


@pytest.mark.django_db
def test_refresh_token(api_client, user):
    obtain = api_client.post(
        reverse("api:token_obtain_pair"),
        {"username": "testuser", "password": "testpass123"},
        format="json",
    )
    refresh = obtain.data["refresh"]
    response = api_client.post(
        reverse("api:token_refresh"),
        {"refresh": refresh},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data


@pytest.mark.django_db
def test_register_success(api_client):
    response = api_client.post(
        reverse("api:register"),
        {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "newpass123",
            "password_confirm": "newpass123",
        },
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert "detail" in response.data
    user = User.objects.get(username="newuser")
    assert user.email == "newuser@example.com"
    assert not user.is_active


@pytest.mark.django_db
def test_register_password_mismatch(api_client):
    response = api_client.post(
        reverse("api:register"),
        {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "newpass123",
            "password_confirm": "different456",
        },
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "password_confirm" in response.data
    assert not User.objects.filter(username="newuser").exists()


@pytest.mark.django_db
def test_register_duplicate_username(api_client, user):
    response = api_client.post(
        reverse("api:register"),
        {
            "username": user.username,
            "email": "other@example.com",
            "password": "newpass123",
            "password_confirm": "newpass123",
        },
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "username" in response.data


@pytest.mark.django_db
def test_register_duplicate_email(api_client, user):
    response = api_client.post(
        reverse("api:register"),
        {
            "username": "another",
            "email": user.email,
            "password": "newpass123",
            "password_confirm": "newpass123",
        },
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data


@pytest.mark.django_db
def test_register_short_password(api_client):
    response = api_client.post(
        reverse("api:register"),
        {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "short",
            "password_confirm": "short",
        },
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "password" in response.data


@pytest.mark.django_db
def test_register_invalid_email(api_client):
    response = api_client.post(
        reverse("api:register"),
        {
            "username": "newuser",
            "email": "not-an-email",
            "password": "newpass123",
            "password_confirm": "newpass123",
        },
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data
