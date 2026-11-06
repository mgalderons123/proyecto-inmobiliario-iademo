import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
def test_home_anonymous(client):
    response = client.get(reverse("core:home"))
    assert response.status_code == 200
    assert "core/home.html" in [template.name for template in response.templates]
    assert "Gestioná tu portfolio inmobiliario".encode() in response.content
    assert b"Ingresar" in response.content
    assert reverse("login").encode() in response.content
    assert reverse("core:register").encode() in response.content


@pytest.mark.django_db
def test_home_authenticated(auth_client, user):
    response = auth_client.get(reverse("core:home"))
    assert response.status_code == 200
    assert b"Bienvenido" in response.content


@pytest.mark.django_db
def test_profile_requires_login(client):
    response = client.get(reverse("core:profile"))
    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_profile_authenticated(auth_client, user):
    response = auth_client.get(reverse("core:profile"))
    assert response.status_code == 200
    assert b"testuser" in response.content
    assert user.email.encode() in response.content


@pytest.mark.django_db
def test_login_view_renders(client):
    response = client.get(reverse("login"))
    assert response.status_code == 200
    assert b"Iniciar sesi" in response.content


@pytest.mark.django_db
def test_register_view_renders(client):
    response = client.get(reverse("core:register"))
    assert response.status_code == 200
    assert b"Crear cuenta" in response.content
    assert "Repetir".encode() in response.content


@pytest.mark.django_db
def test_register_success_redirects_to_verify(client):
    response = client.post(
        reverse("core:register"),
        {
            "username": "newuser",
            "email": "newuser@example.com",
            "password1": "newpass123",
            "password2": "newpass123",
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("core:home") + "?registered=1"
    user = User.objects.get(username="newuser")
    assert user.email == "newuser@example.com"
    assert user.check_password("newpass123")
    assert not user.is_active


@pytest.mark.django_db
def test_register_password_mismatch(client):
    response = client.post(
        reverse("core:register"),
        {
            "username": "newuser",
            "email": "newuser@example.com",
            "password1": "newpass123",
            "password2": "different456",
        },
    )
    assert response.status_code == 200
    assert "no coinciden".encode() in response.content
    assert not User.objects.filter(username="newuser").exists()


@pytest.mark.django_db
def test_register_duplicate_username(client, user):
    response = client.post(
        reverse("core:register"),
        {
            "username": user.username,
            "email": "other@example.com",
            "password1": "newpass123",
            "password2": "newpass123",
        },
    )
    assert response.status_code == 200
    assert User.objects.filter(username=user.username).count() == 1


@pytest.mark.django_db
def test_register_allows_reregistration_of_inactive_user(client):
    from apps.users.models import RegistrationCode

    old_user = User.objects.create_user(
        username="inactive", email="inactive@test.com", password="oldpass123", is_active=False
    )
    RegistrationCode.objects.create(user=old_user, code="111111", expires_at="2027-01-01T00:00:00Z")

    response = client.post(
        reverse("core:register"),
        {
            "username": "inactive",
            "email": "inactive@test.com",
            "password1": "newpass123",
            "password2": "newpass123",
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("core:home") + "?registered=1"
    assert not User.objects.filter(pk=old_user.pk).exists()
    new_user = User.objects.get(username="inactive")
    assert not new_user.is_active


@pytest.mark.django_db
def test_register_blocks_duplicate_active_email(client, user):
    response = client.post(
        reverse("core:register"),
        {
            "username": "other",
            "email": user.email,
            "password1": "newpass123",
            "password2": "newpass123",
        },
    )
    assert response.status_code == 200
    assert not User.objects.filter(username="other").exists()


@pytest.mark.django_db
def test_register_allows_reregistration_of_inactive_email(client):
    from apps.users.models import RegistrationCode

    old_user = User.objects.create_user(
        username="oldname", email="dup@test.com", password="oldpass123", is_active=False
    )
    RegistrationCode.objects.create(user=old_user, code="222222", expires_at="2027-01-01T00:00:00Z")

    response = client.post(
        reverse("core:register"),
        {
            "username": "newname",
            "email": "dup@test.com",
            "password1": "newpass123",
            "password2": "newpass123",
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("core:home") + "?registered=1"
    assert not User.objects.filter(pk=old_user.pk).exists()
    new_user = User.objects.get(username="newname")
    assert not new_user.is_active


@pytest.mark.django_db
def test_register_redirects_authenticated_user(auth_client):
    response = auth_client.get(reverse("core:register"))
    assert response.status_code == 302
    assert response.url == reverse("core:home")


@pytest.mark.django_db
def test_login_remember_me_sets_session_expiry(client, user):
    response = client.post(
        reverse("login"),
        {"username": "testuser", "password": "testpass123", "remember_me": "on"},
    )
    assert response.status_code == 302
    expiry = client.session.get("_session_expiry")
    assert expiry is not None
    assert expiry != 0


@pytest.mark.django_db
def test_login_without_remember_me_leaves_default_expiry(client, user):
    response = client.post(
        reverse("login"),
        {"username": "testuser", "password": "testpass123"},
    )
    assert response.status_code == 302
    assert client.session.get("_session_expiry") == 0


@pytest.mark.django_db
def test_password_reset_page_renders(client):
    response = client.get(reverse("password_reset"))
    assert response.status_code == 200
    assert "¿Olvid".encode() in response.content


@pytest.mark.django_db
def test_password_reset_done_renders(client):
    response = client.get(reverse("password_reset_done"))
    assert response.status_code == 200
    assert b"correo" in response.content.lower()


@pytest.mark.django_db
def test_password_reset_complete_renders(client):
    response = client.get(reverse("password_reset_complete"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_required_password_change_success(auth_client, user):
    from apps.users.models import UserSecurityState

    state, _ = UserSecurityState.objects.update_or_create(
        user=user, defaults={"must_change_password": True}
    )
    response = auth_client.post(
        reverse("core:required_password_change"),
        {
            "old_password": "testpass123",
            "new_password1": "DifferentStrongPassword123!",
            "new_password2": "DifferentStrongPassword123!",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("core:home")
    user.refresh_from_db()
    state.refresh_from_db()
    assert user.check_password("DifferentStrongPassword123!")
    assert state.must_change_password is False
    assert auth_client.get(reverse("core:home")).status_code == 200


@pytest.mark.django_db
def test_required_password_change_rejects_temporary_password(auth_client, user):
    from apps.users.models import UserSecurityState

    UserSecurityState.objects.update_or_create(
        user=user, defaults={"must_change_password": True}
    )
    response = auth_client.post(
        reverse("core:required_password_change"),
        {
            "old_password": "testpass123",
            "new_password1": "testpass123",
            "new_password2": "testpass123",
        },
    )

    assert response.status_code == 200
    assert "La nueva contraseña debe ser diferente de la temporal." in response.content.decode()
    user.refresh_from_db()
    assert user.check_password("testpass123")


@pytest.mark.django_db
def test_password_reset_post_sends_email(client, user, mailoutbox):
    response = client.post(reverse("password_reset"), {"email": user.email})
    assert response.status_code == 302
    assert response.url == reverse("password_reset_done")
    assert len(mailoutbox) == 1
    assert user.email in mailoutbox[0].to
    assert "casarent.app" in mailoutbox[0].body
    assert "example.com" not in mailoutbox[0].body


@pytest.mark.django_db
def test_login_shows_forgot_password_link(client):
    response = client.get(reverse("login"))
    assert "Olvid".encode() in response.content
    assert b'/password_reset/' in response.content


@pytest.mark.django_db
def test_login_shows_custom_domain_link(client):
    response = client.get(reverse("login"))
    assert b"Olvid" in response.content


@pytest.mark.django_db
def test_login_shows_email_login_button(client):
    response = client.get(reverse("login"))
    assert b"Iniciar sesi" in response.content


@pytest.mark.django_db
def test_login_shows_signup_link(client):
    response = client.get(reverse("login"))
    assert "Crear cuenta".encode() in response.content
    assert b'"/register/"' in response.content or b'href="/register/"' in response.content


@pytest.mark.django_db
def test_login_shows_remember_me_checkbox(client):
    response = client.get(reverse("login"))
    assert b'name="remember_me"' in response.content
    assert "Recordarme".encode() in response.content


@pytest.mark.django_db
def test_logout_requires_post(auth_client, user):
    response = auth_client.post(reverse("logout"))
    assert response.status_code == 302
    assert response.url == "/"


@pytest.mark.django_db
def test_logout_get_is_rejected(auth_client, user):
    response = auth_client.get(reverse("logout"))
    assert response.status_code == 405


@pytest.mark.django_db
def test_register_done_renders(client):
    response = client.get(reverse("core:register_done"))
    assert response.status_code == 200
    assert b"Casi listo" in response.content


@pytest.mark.django_db
def test_verify_done_renders_without_param(client):
    response = client.get(reverse("core:verify_done"))
    assert response.status_code == 200
    assert b"inv" in response.content


@pytest.mark.django_db
def test_verify_done_renders_with_valid_param(client):
    response = client.get(reverse("core:verify_done") + "?valid=1")
    assert response.status_code == 200
    assert b"verificado" in response.content


@pytest.mark.django_db
def test_verify_email_invalid_token(client):
    response = client.get(reverse("core:verify_email", kwargs={"token": "bad-token"}))
    assert response.status_code == 302
    assert reverse("core:verify_done") in response.url
    assert "?valid=1" not in response.url


@pytest.mark.django_db
def test_register_creates_inactive_user(client):
    response = client.post(
        reverse("core:register"),
        {
            "username": "verifyuser",
            "email": "verify@example.com",
            "password1": "strongpass123",
            "password2": "strongpass123",
        },
    )
    assert response.status_code == 302
    user = User.objects.get(username="verifyuser")
    assert not user.is_active


@pytest.mark.django_db
def test_register_creates_registration_code(client):
    from apps.users.models import RegistrationCode

    response = client.post(
        reverse("core:register"),
        {
            "username": "codeuser",
            "email": "code@example.com",
            "password1": "strongpass123",
            "password2": "strongpass123",
        },
    )
    assert response.status_code == 302
    user = User.objects.get(username="codeuser")
    reg_code = RegistrationCode.objects.get(user=user)
    assert len(reg_code.code) == 6
    assert reg_code.code.isdigit()
    assert not reg_code.used
    assert reg_code.expires_at is not None


@pytest.mark.django_db
def test_register_email_contains_code(client, mailoutbox):
    response = client.post(
        reverse("core:register"),
        {
            "username": "emailuser",
            "email": "email@example.com",
            "password1": "strongpass123",
            "password2": "strongpass123",
        },
    )
    assert response.status_code == 302
    assert len(mailoutbox) == 1
    body = mailoutbox[0].body
    assert "código de seguridad" in body
    assert "casarent.app" in body
    assert "example.com" not in body
    import re

    match = re.search(r"(\d{6})", body)
    assert match is not None
    assert len(match.group(1)) == 6


@pytest.mark.parametrize(
    ("accept_language", "expected_language", "expected_subject", "expected_text"),
    [
        ("es-AR,es;q=0.9", "es", "Verificá tu correo electrónico", "Hacé clic"),
        ("en-US,en;q=0.9", "en", "Verify your email address", "Click the following link"),
        ("pt-BR,pt;q=0.9", "pt", "Verifique seu endereço de e-mail", "Clique no link a seguir"),
        ("de-DE,de;q=0.9", "es", "Verificá tu correo electrónico", "Hacé clic"),
    ],
)
@pytest.mark.django_db
def test_register_email_uses_browser_language(
    client,
    mailoutbox,
    accept_language,
    expected_language,
    expected_subject,
    expected_text,
):
    from apps.users.models import UserTheme

    username = f"browser-{expected_language}"
    response = client.post(
        reverse("core:register"),
        {
            "username": username,
            "email": f"{username}@casarent.test",
            "password1": "strongpass123",
            "password2": "strongpass123",
        },
        HTTP_ACCEPT_LANGUAGE=accept_language,
    )

    assert response.status_code == 302
    user = User.objects.get(username=username)
    assert UserTheme.objects.get(user=user).language == expected_language
    assert mailoutbox[0].subject == expected_subject
    assert expected_text in mailoutbox[0].body
    assert "casarent.app" in mailoutbox[0].body


@pytest.mark.django_db
def test_verification_email_uses_recipient_language(client, user, mailoutbox):
    from apps.users.models import UserTheme
    from apps.users.services import send_verification_email

    UserTheme.objects.create(user=user, language=UserTheme.Languages.PORTUGUES)
    request = client.get(
        reverse("core:home"), HTTP_ACCEPT_LANGUAGE="es-AR,es;q=0.9"
    ).wsgi_request

    send_verification_email(user, request)

    assert mailoutbox[0].subject == "Verifique seu endereço de e-mail"
    assert "Clique no link a seguir" in mailoutbox[0].body
    assert "Hacé clic" not in mailoutbox[0].body


@pytest.mark.django_db
def test_verify_email_shows_code(client, user):
    from apps.users.services import make_verification_token
    from apps.users.models import RegistrationCode

    reg_code = RegistrationCode.objects.create(
        user=user,
        code="123456",
        expires_at="2027-01-01T00:00:00Z",
    )
    token = make_verification_token(user)
    response = client.get(reverse("core:verify_email", kwargs={"token": token}))
    assert response.status_code == 302
    assert "code=123456" in response.url
    assert "valid=1" in response.url


@pytest.mark.django_db
def test_verify_done_displays_code(client):
    response = client.get(reverse("core:verify_done") + "?valid=1&code=123456")
    assert response.status_code == 200
    assert b"123456" in response.content
    assert b"verificado" in response.content


@pytest.mark.django_db
def test_login_with_security_code_succeeds(client, user):
    from apps.users.models import PrivacyConsent, RegistrationCode

    user.is_active = True
    user.save(update_fields=["is_active"])
    RegistrationCode.objects.create(
        user=user,
        code="654321",
        expires_at="2027-01-01T00:00:00Z",
    )
    response = client.post(
        reverse("login"),
        {
            "username": "testuser",
            "password": "testpass123",
            "security_code": "654321",
            "privacy_consent": "on",
        },
        REMOTE_ADDR="198.51.100.24",
        HTTP_USER_AGENT="Casarent acceptance test",
    )
    assert response.status_code == 302
    assert response.url == reverse("core:home")
    reg_code = RegistrationCode.objects.get(user=user)
    assert reg_code.used
    consent = PrivacyConsent.objects.get(user=user)
    assert consent.policy_version == "temporary-2026-10"
    assert consent.accepted_at is not None
    assert str(consent.ip_address) == "198.51.100.24"
    assert consent.user_agent == "Casarent acceptance test"


@pytest.mark.django_db
def test_login_with_security_code_requires_privacy_consent(client, user):
    from apps.users.models import PrivacyConsent, RegistrationCode

    user.is_active = True
    user.save(update_fields=["is_active"])
    reg_code = RegistrationCode.objects.create(
        user=user,
        code="654321",
        expires_at="2027-01-01T00:00:00Z",
    )

    response = client.post(
        reverse("login"),
        {
            "username": "testuser",
            "password": "testpass123",
            "security_code": "654321",
        },
    )

    assert response.status_code == 200
    assert "Debés aceptar".encode() in response.content
    assert b'id="code-overlay"' in response.content
    assert b'id="code-form-errors"' in response.content
    assert b'name="privacy_consent"' in response.content
    assert b'aria-invalid="true"' in response.content
    assert b'href="/"' in response.content
    assert b'target="_blank"' in response.content
    reg_code.refresh_from_db()
    assert not reg_code.used
    assert not PrivacyConsent.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_login_with_wrong_security_code_fails(client, user):
    from apps.users.models import RegistrationCode

    user.is_active = True
    user.save(update_fields=["is_active"])
    RegistrationCode.objects.create(
        user=user,
        code="654321",
        expires_at="2027-01-01T00:00:00Z",
    )
    response = client.post(
        reverse("login"),
        {
            "username": "testuser",
            "password": "testpass123",
            "security_code": "000000",
            "privacy_consent": "on",
        },
    )
    assert response.status_code == 200
    assert b"incorrecto" in response.content


@pytest.mark.django_db
def test_login_without_security_code_when_required_shows_popup(client, user):
    from apps.users.models import RegistrationCode

    user.is_active = True
    user.save(update_fields=["is_active"])
    RegistrationCode.objects.create(
        user=user,
        code="654321",
        expires_at="2027-01-01T00:00:00Z",
    )
    response = client.post(
        reverse("login"),
        {
            "username": "testuser",
            "password": "testpass123",
        },
    )
    assert response.status_code == 200
    assert b"C\x30digo de seguridad" in response.content or b"C\xc3\xb3digo de seguridad" in response.content or b"seguridad" in response.content.lower()


@pytest.mark.django_db
def test_login_popup_with_valid_code_succeeds(client, user):
    from apps.users.models import RegistrationCode

    user.is_active = True
    user.save(update_fields=["is_active"])
    RegistrationCode.objects.create(
        user=user,
        code="654321",
        expires_at="2027-01-01T00:00:00Z",
    )
    response = client.post(
        reverse("login"),
        {
            "username": "testuser",
            "password": "testpass123",
        },
    )
    assert response.status_code == 200

    response = client.post(
        reverse("login"),
        {
            "username": "testuser",
            "password": "testpass123",
            "security_code": "654321",
            "privacy_consent": "on",
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("core:home")
    reg_code = RegistrationCode.objects.get(user=user)
    assert reg_code.used


@pytest.mark.django_db
def test_login_popup_with_invalid_code_shows_error(client, user):
    from apps.users.models import RegistrationCode

    user.is_active = True
    user.save(update_fields=["is_active"])
    RegistrationCode.objects.create(
        user=user,
        code="654321",
        expires_at="2027-01-01T00:00:00Z",
    )
    client.post(
        reverse("login"),
        {
            "username": "testuser",
            "password": "testpass123",
        },
    )
    response = client.post(
        reverse("login"),
        {
            "username": "testuser",
            "password": "testpass123",
            "security_code": "000000",
            "privacy_consent": "on",
        },
    )
    assert response.status_code == 200
    assert b"incorrecto" in response.content


@pytest.mark.django_db
def test_login_with_email_succeeds(client, user):
    from apps.users.models import PrivacyConsent

    user.is_active = True
    user.save(update_fields=["is_active"])
    response = client.post(
        reverse("login"),
        {
            "username": "testuser@example.com",
            "password": "testpass123",
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("core:home")
    assert not PrivacyConsent.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_login_with_email_case_insensitive(client, user):
    user.is_active = True
    user.save(update_fields=["is_active"])
    response = client.post(
        reverse("login"),
        {
            "username": "TestUser@Example.COM",
            "password": "testpass123",
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("core:home")


@pytest.mark.django_db
def test_login_with_nonexistent_email_fails(client, user):
    user.is_active = True
    user.save(update_fields=["is_active"])
    response = client.post(
        reverse("login"),
        {
            "username": "noexiste@correo.com",
            "password": "testpass123",
        },
    )
    assert response.status_code == 200
    assert b"introduzca" in response.content.lower()


@pytest.mark.django_db
def test_login_creates_login_log(client, user):
    from apps.users.models import LoginLog

    assert LoginLog.objects.count() == 0
    client.post(
        reverse("login"),
        {"username": "testuser", "password": "testpass123"},
    )
    assert LoginLog.objects.count() == 1
    log = LoginLog.objects.first()
    assert log.user == user


@pytest.mark.django_db
def test_login_log_stores_ip_and_user_agent(client, user):
    from apps.users.models import LoginLog

    client.post(
        reverse("login"),
        {"username": "testuser", "password": "testpass123"},
        REMOTE_ADDR="192.168.1.1",
        HTTP_USER_AGENT="TestBrowser/1.0",
    )
    log = LoginLog.objects.first()
    assert log.ip_address == "192.168.1.1"
    assert log.user_agent == "TestBrowser/1.0"


@pytest.mark.django_db
def test_bitacora_requires_login(client):
    response = client.get(reverse("core:bitacora"))
    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_bitacora_allows_account_owner(auth_client, user):
    response = auth_client.get(reverse("core:bitacora"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_bitacora_accessible_by_staff(auth_client, user):
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    response = auth_client.get(reverse("core:bitacora"))
    assert response.status_code == 200
    assert b"Bit" in response.content


@pytest.mark.django_db
def test_bitacora_displays_login_logs(auth_client, user):
    from apps.users.models import LoginLog

    user.is_staff = True
    user.save(update_fields=["is_staff"])
    LoginLog.objects.create(user=user, ip_address="10.0.0.1", user_agent="Agent/1.0")
    response = auth_client.get(reverse("core:bitacora"))
    assert response.status_code == 200
    assert b"10.0.0.1" in response.content


@pytest.mark.django_db
def test_profile_shows_bitacora_link_for_staff(auth_client, user):
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    response = auth_client.get(reverse("core:profile"))
    assert response.status_code == 200
    assert "Bit" in response.content.decode()


@pytest.mark.django_db
def test_profile_hides_bitacora_link_for_non_staff(auth_client, user):
    response = auth_client.get(reverse("core:profile"))
    assert response.status_code == 200
    assert "bitacora" not in response.content.decode().lower()


@pytest.mark.django_db
def test_home_has_favicon(client):
    response = client.get(reverse("core:home"))
    assert response.status_code == 200
    assert b'rel="icon"' in response.content
    assert b"image/svg+xml" in response.content


@pytest.mark.django_db
def test_admin_users_allows_account_owner(auth_client, user):
    response = auth_client.get(reverse("core:admin_users"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_users_requires_login(client):
    response = client.get(reverse("core:admin_users"))
    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_admin_users_renders(auth_client, user):
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    response = auth_client.get(reverse("core:admin_users"))
    assert response.status_code == 200
    assert b"Gestionar Usuarios" in response.content
    assert user.username.encode() in response.content


@pytest.mark.django_db
def test_admin_users_search(auth_client, user):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    User.objects.create_user(username="other", email="other@test.com", password="pass12345")
    response = auth_client.get(reverse("core:admin_users") + "?q=other")
    assert response.status_code == 200
    assert b"other" in response.content
    assert user.username.encode() not in response.content.split(b"other")[0][-50:]


@pytest.mark.django_db
def test_admin_user_edit_renders(auth_client, user):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user.is_staff = True
    user.is_superuser = True
    user.save(update_fields=["is_staff", "is_superuser"])
    other = User.objects.create_user(username="editable", email="e@e.com", password="pass12345")
    response = auth_client.get(reverse("core:admin_user_edit", kwargs={"pk": other.pk}))
    assert response.status_code == 200
    assert b"editable" in response.content


@pytest.mark.django_db
def test_admin_user_edit_updates(auth_client, user):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user.is_staff = True
    user.is_superuser = True
    user.save(update_fields=["is_staff", "is_superuser"])
    other = User.objects.create_user(username="editable", email="old@test.com", password="pass12345")
    response = auth_client.post(
        reverse("core:admin_user_edit", kwargs={"pk": other.pk}),
        {"action": "edit", "email": "new@test.com", "is_staff": "on"},
    )
    assert response.status_code == 302
    other.refresh_from_db()
    assert other.email == "new@test.com"
    assert other.is_staff is True


@pytest.mark.django_db
def test_admin_user_edit_own_account_blocked(auth_client, user):
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    response = auth_client.get(reverse("core:admin_user_edit", kwargs={"pk": user.pk}))
    assert response.status_code == 302
    assert response.url == reverse("core:admin_users")


@pytest.mark.django_db
def test_admin_user_toggle_active(auth_client, user):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user.is_staff = True
    user.is_superuser = True
    user.save(update_fields=["is_staff", "is_superuser"])
    other = User.objects.create_user(username="toggleme", email="t@t.com", password="pass12345")
    assert other.is_active is True
    response = auth_client.post(reverse("core:admin_user_toggle_active", kwargs={"pk": other.pk}))
    assert response.status_code == 302
    other.refresh_from_db()
    assert other.is_active is False


@pytest.mark.django_db
def test_admin_user_delete(auth_client, user):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user.is_staff = True
    user.is_superuser = True
    user.save(update_fields=["is_staff", "is_superuser"])
    other = User.objects.create_user(username="deleteme", email="d@d.com", password="pass12345")
    response = auth_client.post(reverse("core:admin_user_delete", kwargs={"pk": other.pk}))
    assert response.status_code == 302
    assert not User.objects.filter(pk=other.pk).exists()


@pytest.mark.django_db
def test_admin_user_delete_self_blocked(auth_client, user):
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    response = auth_client.post(reverse("core:admin_user_delete", kwargs={"pk": user.pk}))
    assert response.status_code == 302
    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_admin_user_reset_password(auth_client, user):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user.is_staff = True
    user.is_superuser = True
    user.save(update_fields=["is_staff", "is_superuser"])
    other = User.objects.create_user(username="resetpwd", email="r@r.com", password="oldpass123")
    response = auth_client.post(
        reverse("core:admin_user_edit", kwargs={"pk": other.pk}),
        {"action": "reset_password", "new_password": "newpass123"},
    )
    assert response.status_code == 302
    other.refresh_from_db()
    assert other.check_password("newpass123")


@pytest.mark.django_db
def test_admin_user_regenerate_code(auth_client, user, mailoutbox):
    from django.contrib.auth import get_user_model
    from apps.users.models import RegistrationCode

    User = get_user_model()
    user.is_staff = True
    user.is_superuser = True
    user.save(update_fields=["is_staff", "is_superuser"])
    other = User.objects.create_user(username="regencode", email="rc@rc.com", password="pass12345")
    RegistrationCode.objects.create(user=other, code="111111", expires_at="2027-01-01T00:00:00Z")
    response = auth_client.post(reverse("core:admin_user_edit", kwargs={"pk": other.pk}), {"action": "regenerate_code"})
    assert response.status_code == 302
    assert len(mailoutbox) == 1
    new_code = RegistrationCode.objects.filter(user=other).order_by("-created_at").first()
    assert new_code.code != "111111"
    assert len(new_code.code) == 6


@pytest.mark.django_db
def test_admin_user_edit_email_superadmin(auth_client, user):
    """SuperAdmin puede editar email de otro usuario."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user.is_staff = True
    user.is_superuser = True
    user.save(update_fields=["is_staff", "is_superuser"])
    other = User.objects.create_user(username="editemail", email="old@test.com", password="pass12345")
    response = auth_client.post(
        reverse("core:admin_user_edit_email", kwargs={"pk": other.pk}),
        {"email": "new@test.com"},
    )
    assert response.status_code == 302
    other.refresh_from_db()
    assert other.email == "new@test.com"


@pytest.mark.django_db
def test_admin_user_edit_email_admincuenta_fall(auth_client, user):
    """AdminCuenta no puede editar email (redirige con error)."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user.is_staff = True
    user.is_superuser = False
    user.save(update_fields=["is_staff", "is_superuser"])
    other = User.objects.create_user(username="noedit", email="no@test.com", password="pass12345")
    response = auth_client.post(
        reverse("core:admin_user_edit_email", kwargs={"pk": other.pk}),
        {"email": "hacked@test.com"},
    )
    assert response.status_code == 302
    other.refresh_from_db()
    assert other.email == "no@test.com"


@pytest.mark.django_db
def test_admin_user_edit_email_self_fall(auth_client, user):
    """No se puede cambiar el propio email desde esta vista."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user.is_staff = True
    user.is_superuser = True
    user.save(update_fields=["is_staff", "is_superuser"])
    original_email = user.email
    response = auth_client.post(
        reverse("core:admin_user_edit_email", kwargs={"pk": user.pk}),
        {"email": "self@test.com"},
    )
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.email == original_email


@pytest.mark.django_db
def test_admin_user_edit_email_empty_fall(auth_client, user):
    """Email vacío muestra error y no cambia."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user.is_staff = True
    user.is_superuser = True
    user.save(update_fields=["is_staff", "is_superuser"])
    other = User.objects.create_user(username="emptymail", email="original@test.com", password="pass12345")
    response = auth_client.post(
        reverse("core:admin_user_edit_email", kwargs={"pk": other.pk}),
        {"email": ""},
    )
    assert response.status_code == 302
    other.refresh_from_db()
    assert other.email == "original@test.com"


@pytest.mark.django_db
def test_admin_user_edit_email_renders_in_list(auth_client, user):
    """El icono de lápiz aparece en la lista para SuperAdmin."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user.is_staff = True
    user.is_superuser = True
    user.save(update_fields=["is_staff", "is_superuser"])
    User.objects.create_user(username="shown", email="show@test.com", password="pass12345")
    response = auth_client.get(reverse("core:admin_users"))
    assert response.status_code == 200
    assert b'enableEmailEdit' in response.content


@pytest.mark.django_db
def test_admin_user_edit_email_no_render_for_admincuenta(auth_client, user):
    """AdminCuenta NO ve el icono de lápiz en la lista."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user.is_staff = True
    user.is_superuser = False
    user.save(update_fields=["is_staff", "is_superuser"])
    User.objects.create_user(username="otherone", email="oo@test.com", password="pass12345")
    response = auth_client.get(reverse("core:admin_users"))
    assert response.status_code == 200
    assert b'enableEmailEdit' not in response.content


@pytest.mark.django_db
def test_home_shows_registration_popup(client):
    response = client.get(reverse("core:home") + "?registered=1")
    assert response.status_code == 200
    assert b"Revis" in response.content
    assert b"correo" in response.content.lower()
    assert b"regModal" in response.content


@pytest.mark.django_db
def test_home_hides_registration_popup_without_param(client):
    response = client.get(reverse("core:home"))
    assert response.status_code == 200
    assert b'display:none' in response.content
