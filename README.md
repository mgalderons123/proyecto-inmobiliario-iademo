# PRY_INMOB

Aplicación web en Django con vistas tradicionales (templates), una API REST
con autenticación JWT y PostgreSQL como base de datos persistente.

## Versión actual

CasaRent gestiona cuentas y membresías, propiedades, propietarios, inquilinos,
contratos, cuotas, pagos y reportes. Incluye una web con sesiones y una API con
JWT, aislamiento por cuenta y almacenamiento separado para documentos privados.

La configuración Docker mantiene desarrollo, QA y producción en entornos
independientes. Producción utiliza PostgreSQL con TLS, Redis, Gunicorn, Nginx y
Cloudflare Tunnel para publicar `https://casarent.app` desde el servidor local.
Consulta [la guía de producción y respaldos](PRODUCTION.md) antes de desplegar.
Los secretos, datos y documentos no forman parte del repositorio.

## Stack

- **Python** 3.12+
- **Django** 5.x
- **Django REST Framework** + `djangorestframework-simplejwt` (JWT)
- **PostgreSQL** 16
- **Templates** Django + sesiones para la web
- **python-decouple** para variables de entorno
- **pytest** + **pytest-django` para tests

## Requisitos

- Python 3.12 o superior
- pip
- Docker Desktop
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

# 5. Levantar PostgreSQL y el servidor de desarrollo
./scripts/dev.sh
# La primera ejecucion genera .env.postgres con permisos 0600.
# Equivale a: postgres-up + migrate + ensure_superuser + runserver_dev

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
| `ALLOWED_HOSTS` | Sí        | —       | Hosts permitidos (CSV).                |
| `POSTGRES_DB` | No | `casarent_dev` | Nombre de la base local. |
| `POSTGRES_USER` | No | `casarent_dev` | Usuario de la base local. |
| `POSTGRES_PASSWORD` | Sí | — | Contraseña de PostgreSQL. |
| `POSTGRES_HOST` | No | `127.0.0.1` | Host de PostgreSQL. |
| `POSTGRES_PORT` | No | `5432` | Puerto de PostgreSQL. |

En desarrollo, `./scripts/postgres-up.sh` genera estas variables en
`.env.postgres`. Las variables del proceso y `.env` tienen precedencia.

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
| `/`                        | Landing pública / resumen operativo | Mixta |
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
set -a; source .env.postgres; set +a
pytest
```

- `pytest-django` crea una base PostgreSQL aislada por ejecución.
- Cobertura incluida:
  - `tests/test_web.py` → vistas con templates, login, registro, password
    reset, recordarme, logout POST-only.
  - `tests/test_api.py` → endpoints REST, JWT, usuario autenticado.

### Verificación incremental

Para no repetir una ejecución idéntica cuando no cambió ningún input:

```bash
./scripts/verify-changed.py
./scripts/verify-changed.py -- tests/test_web.py -x
./scripts/verify-changed.py --force
```

La herramienta guarda únicamente resultados exitosos en `.cache/`, usando una
huella del código, dependencias, versión de Python, settings y comando. Los
cambios globales y las validaciones previas a despliegue deben seguir ejecutando
la suite completa.

Para comparar el landing público de desarrollo y QA:

```bash
./scripts/compare-envs.py
./scripts/compare-envs.py --force
```

La comparación normaliza los hashes de archivos estáticos y se reutiliza solo
si no cambiaron el código local ni la imagen Docker de QA.

## Ambiente QA local

El stack QA es independiente del desarrollo en el puerto 4000 y utiliza
Docker Compose con PostgreSQL, Redis, Mailpit y Gunicorn.

### Requisitos

- Docker Desktop iniciado.
- Puertos locales `4100` y `8025` disponibles.

### Iniciar

```bash
./scripts/qa-up.sh
```

La primera ejecución crea `.env.qa` con secretos y contraseñas aleatorias,
permisos `0600`, construye las imágenes, aplica migraciones y carga datos
sintéticos idempotentes.

- Aplicación: `http://localhost:4100`
- Mailpit: `http://localhost:8025`
- Credenciales locales: `.env.qa`

Usuarios sintéticos:

- `qa-superadmin`
- `qa-admin-a`
- `qa-admin-b`
- `qa-inquilino-a`
- `qa-inquilino-b`

### Ejecutar tests en PostgreSQL

```bash
./scripts/qa-test.sh
```

Se pueden pasar argumentos adicionales a pytest:

```bash
./scripts/qa-test.sh tests/test_api.py -x
```

### Operaciones

```bash
./scripts/qa-seed.sh       # reconstruye el dataset sintético
./scripts/qa-down.sh       # detiene QA y conserva datos
./scripts/qa-reset.sh      # solicita confirmación y elimina volúmenes QA
./scripts/qa-reset.sh --yes
./scripts/qa-security.sh   # Django check, Bandit y pip-audit
```

PostgreSQL y Redis no publican puertos en el host. Los volúmenes y servicios
usan el proyecto Compose `casarent-qa`, por lo que no interfieren con el
ambiente de desarrollo.

### Caché de aplicación

- Desarrollo usa caché en memoria y desactiva por defecto el caché del landing.
- QA usa Redis con espacios de claves separados para aplicación y rate limiting.
- Producción requiere `REDIS_URL` y usa prefijos independientes de QA.
- El landing anónimo se cachea por idioma durante 300 segundos, configurable
  con `PUBLIC_LANDING_CACHE_TIMEOUT`.
- Las respuestas públicas incluyen `ETag` y revalidación privada. Login, JWT,
  dashboard autenticado y medios privados no se cachean como páginas.

## Notas sobre la DB

El entorno de desarrollo usa el proyecto Compose `casarent-dev`. PostgreSQL
se publica exclusivamente en `127.0.0.1:5432` y persiste sus datos en el
volumen `dev_postgres`.

```bash
./scripts/postgres-up.sh    # inicia PostgreSQL y conserva los datos
./scripts/postgres-down.sh  # detiene PostgreSQL y conserva el volumen
./scripts/dev.sh            # inicia DB, migra y levanta Django
```

`db.sqlite3` se conserva solamente como respaldo de la migración inicial y
está excluido de Git. Producción debe usar `PRY_INMOB.settings_production`,
credenciales administradas externamente y una conexión PostgreSQL con TLS.

## Licencia

MIT (o la que defina el proyecto).
# proyecto-inmobiliario-iademo
