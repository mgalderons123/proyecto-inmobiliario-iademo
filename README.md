# PRY_INMOB

Aplicación web en Django con vistas tradicionales (templates) y una API REST
con autenticación JWT. La base de datos es un SQLite local que se recrea
automáticamente al iniciar el server (no persiste entre reinicios). Pensado
para desarrollo, demos y prototipos descartables.

## Stack

- **Python** 3.12+
- **Django** 5.x
- **Django REST Framework** + `djangorestframework-simplejwt` (JWT)
- **SQLite en archivo** (`db.sqlite3`, recreado en cada arranque)
- **Templates** Django + sesiones para la web
- **python-decouple** para variables de entorno
- **pytest** + **pytest-django` para tests

## Requisitos

- Python 3.12 o superior
- pip
- (Opcional) virtualenv

## Instalación

```bash
# 1. Clonar e ingresar al proyecto
git clone <repo-url> PRY_INMOB
cd PRY_INMOB

# 2. Crear y activar entorno virtual
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env y definir SECRET_KEY (y opcionalmente DEBUG)

# 5. (Dev) Levantar el server con bootstrap de DB
./scripts/dev.sh
# Equivale a: migrate + create default superuser + runserver_dev
# Default: admin / admin12345 (configurable via DJANGO_SUPERUSER_*)

# 5b. (Producción-like) Flujo manual
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

> El server de dev (`runserver_dev`) es opt-in y vive en `apps/devtools/`.
> El `runserver` estándar de Django no toca la DB.

## Variables de entorno

Definidas en `.env` (ver `.env.example`):

| Variable      | Obligatoria | Default | Descripción                            |
|---------------|-------------|---------|----------------------------------------|
| `SECRET_KEY`  | Sí          | —       | Clave secreta de Django.               |
| `DEBUG`       | No          | `False` | `True` para activar modo debug.        |
| `ALLOWED_HOSTS` | No        | `*`     | Hosts permitidos (CSV).                |

## Estructura del proyecto

```
PRY_INMOB/
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
├── pytest.ini
├── conftest.py
├── scripts/
│   └── dev.sh                # Bootstrap dev (migrate + superuser + runserver_dev)
├── PRY_INMOB/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── core/                  # Vistas web con templates
│   │   ├── apps.py
│   │   ├── forms.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── templates/
│   │       ├── core/
│   │       │   ├── base.html
│   │       │   ├── auth_base.html
│   │       │   ├── home.html
│   │       │   ├── profile.html
│   │       │   ├── login.html
│   │       │   └── register.html
│   │       └── registration/
│   │           ├── password_reset_form.html
│   │           ├── password_reset_done.html
│   │           ├── password_reset_confirm.html
│   │           └── password_reset_complete.html
│   ├── api/                   # Endpoints REST
│   │   ├── apps.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── auth_urls.py
│   ├── users/                 # Lógica de negocio compartida
│   │   └── services.py
│   └── devtools/              # Comandos solo de dev
│       ├── apps.py
│       └── management/commands/runserver_dev.py
└── tests/
    ├── test_web.py
    └── test_api.py
```

## Rutas principales

### Web (templates + sesiones)

| URL                        | Vista                            | Auth    |
|----------------------------|----------------------------------|---------|
| `/`                        | Home                             | Pública |
| `/login/`                  | `CustomLoginView` (Django)       | Pública |
| `/logout/`                 | `LogoutView` (Django, POST)      | Sesión  |
| `/register/`               | Registro                         | Pública |
| `/profile/`                | Perfil                           | Sesión  |
| `/password_reset/`         | Recuperar contraseña             | Pública |
| `/password_reset/done/`    | Confirmación de envío            | Pública |
| `/reset/<uidb64>/<token>/` | Nueva contraseña                 | Pública |
| `/reset/done/`             | Contraseña cambiada              | Pública |
| `/admin/`                  | Admin de Django                  | Staff   |

### API REST (JWT)

| Método | URL                          | Descripción                       | Auth |
|--------|------------------------------|-----------------------------------|------|
| POST   | `/api/auth/register/`        | Registrar un usuario nuevo        | —    |
| POST   | `/api/auth/token/`           | Obtener `access` + `refresh` JWT  | —    |
| POST   | `/api/auth/token/refresh/`   | Refrescar `access`                | —    |
| GET    | `/api/v1/me/`                | Devuelve el usuario autenticado   | JWT  |

#### Ejemplo: registrar usuario

```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "juanp",
    "email": "juanp@example.com",
    "password": "secreto123",
    "password_confirm": "secreto123"
  }'
```

Respuesta (`201 Created`):

```json
{ "id": 2, "username": "juanp", "email": "juanp@example.com" }
```

Si las contraseñas no coinciden devuelve `400` con detalle en el campo
`password_confirm`. Si el `username` o `email` ya existen, devuelve `400`
con detalle en el campo correspondiente.

#### Ejemplo: obtener token

```bash
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'
```

Respuesta:

```json
{
  "access": "eyJhbGciOi...",
  "refresh": "eyJhbGciOi..."
}
```

#### Ejemplo: endpoint protegido

```bash
curl http://localhost:8000/api/v1/me/ \
  -H "Authorization: Bearer <access_token>"
```

## Autenticación

- **Web** → usa el sistema de sesiones de Django (`django.contrib.auth`).
  El usuario se loguea en `/login/` y navega con cookie de sesión.
  El checkbox "Recordarme" extiende la duración de la sesión a 14 días
  (configurable en `apps/core/forms.py:REMEMBER_ME_DURATION`).
- **API** → usa JWT firmado con `SECRET_KEY`. El cliente debe enviar
  el header `Authorization: Bearer <access>` en cada request.
- **Password reset** → flujo estándar de Django, envía email con enlace
  firmado (1 h de expiración). En dev se imprime en consola.
- Ambos sistemas comparten el mismo modelo `User`, por lo que un usuario
  creado desde el admin sirve tanto para login web como para pedir tokens.

## UI / Estilo

El layout está inspirado en Salesforce login:

- Sidebar azul a gradiente con logo, nav y datos de usuario.
- Card central para el contenido (form de login, registro, perfil, etc.).
- Login tiene: nombre de usuario + contraseña, **detector de Bloq Mayús** (JS),
  "Recordarme", "¿Olvidó la contraseña?", "Utilizar dominio personalizado"
  (maqueta), "Iniciar sesión con correo electrónico" (maqueta), y CTA al registro.
- Responsive: en mobile el sidebar se aplana a una barra superior.
- CSS inline en `apps/core/templates/core/base.html` (~250 LOC), sin `staticfiles`.

## Tests

```bash
pytest
```

- `pytest-django` usa SQLite in-memory por test (consistente con el stack).
- Cobertura incluida:
  - `tests/test_web.py` → vistas con templates, login, registro, password
    reset, recordarme, logout POST-only.
  - `tests/test_api.py` → endpoints REST, JWT, usuario autenticado.

## Notas sobre la DB

Se usa un archivo SQLite local (`db.sqlite3`) en lugar de `:memory:` porque
SQLite en memoria real no se puede compartir entre conexiones, lo que rompe
el patrón request-response de Django (cada request abre su propia conexión).

Para DB descartable, `./scripts/dev.sh` aplica migraciones y crea un
superusuario `admin` / `admin12345` (configurable via `DJANGO_SUPERUSER_*`)
antes de levantar el server con `runserver_dev`.

Para una DB persistente real, usá `python manage.py migrate` + `runserver`
estándar (no `runserver_dev`).

## Licencia

MIT (o la que defina el proyecto).
# proyecto-inmobiliario-iademo
