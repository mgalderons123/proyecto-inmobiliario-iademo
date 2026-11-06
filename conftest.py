import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


@pytest.fixture(autouse=True)
def _disable_ratelimit():
    original = settings.RATELIMIT_ENABLE
    settings.RATELIMIT_ENABLE = False
    yield
    settings.RATELIMIT_ENABLE = original


@pytest.fixture
def user(db):
    user = User.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="testpass123",
    )
    from apps.users.accounts import ensure_account_for_user

    account = ensure_account_for_user(user)
    account.plan = account.Planes.PROFESIONAL
    account.save(update_fields=["plan"])
    return user


@pytest.fixture
def auth_client(client, user):
    client.login(username=user.username, password="testpass123")
    return client


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def jwt_client(api_client, user):
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client
