# Puesta en producción

Dominio publicado: https://casarent.app mediante Cloudflare Tunnel.
Servidor: esta máquina, con Docker Desktop y `compose.production.yml`.

Publicación realizada el 5 de noviembre de 2026. PostgreSQL, Redis, Django,
Nginx y cloudflared están en contenedores independientes. Se trasladó una copia
de los datos y archivos de desarrollo, conservando la clave de cifrado; desarrollo
y QA siguen separados. Los usuarios mantienen sus contraseñas existentes.

Validaciones: HTTPS público, página principal y login HTTP 200, healthcheck,
conexión PostgreSQL con TLS, lectura de campos cifrados, archivos referenciados,
autenticación SMTP sin enviar mensajes, y suite completa de 245 pruebas.
La restauración inicial usó el respaldo de desarrollo; el respaldo posterior de
producción debe probarse también en una restauración aislada y conservarse cifrado
fuera de esta máquina.

## Configuración y claves

Usar PRY_INMOB.settings_production y suministrar desde el gestor de secretos:
SECRET_KEY, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST,
REDIS_URL, PII_ENCRYPTION_KEY y JWT_SIGNING_KEY. Definir DEBUG=False,
ALLOWED_HOSTS y CSRF_TRUSTED_ORIGINS para el dominio real. Mantener PostgreSQL
y Redis en red privada; usar TLS de PostgreSQL con certificado verificable.

Para datos existentes, PII_ENCRYPTION_KEY debe conservar exactamente el secreto
que cifró esos datos (históricamente SECRET_KEY si no había clave específica).
No generar una clave nueva para una base existente sin un proceso de recifrado
verificado. Respaldar las claves por un canal protegido separado de los datos.
Cambiar JWT_SIGNING_KEY invalida los tokens emitidos anteriormente.

Configurar correo SMTP real mediante EMAIL_BACKEND, EMAIL_HOST, EMAIL_PORT,
EMAIL_HOST_USER, EMAIL_HOST_PASSWORD y EMAIL_USE_TLS según el proveedor;
comprobar registro, recuperación de contraseña e invitaciones.

## Publicación de una versión

1. Construir una imagen identificada por versión y conservar la anterior.
2. Ejecutar la suite completa con scripts/verify-changed.py en PostgreSQL.
3. Respaldar base de datos, MEDIA_ROOT y PRIVATE_MEDIA_ROOT.
4. En un único trabajo de publicación, con settings de producción, ejecutar:
   python manage.py check --deploy --fail-level WARNING
   python manage.py migrate --noinput
   python manage.py collectstatic --noinput
5. Iniciar scripts/production-entrypoint.sh mediante /bin/sh, detrás de un proxy
   HTTPS. La imagen actual también selecciona ese arranque si recibe
   DJANGO_SETTINGS_MODULE=PRY_INMOB.settings_production.
6. Montar almacenamiento persistente para medios. El proxy puede servir medios
   públicos, pero jamás debe publicar PRIVATE_MEDIA_ROOT. WhiteNoise sirve
   archivos estáticos; las descargas privadas pasan por las vistas autorizadas.
7. Comprobar /health/, inicio de sesión, operación por cuenta y descargas privadas.

El arranque de producción no migra ni carga datos sintéticos. La recolección de
estáticos debe ejecutarse en la misma imagen o volumen que utilizarán los workers.
Verificar que el proxy sobrescriba X-Forwarded-Proto antes de habilitar
BEHIND_HTTPS_PROXY=True.

## Recuperación y operación

Programar respaldos cifrados de PostgreSQL y ambos almacenes de archivos, con
retención y acceso restringido. Antes del lanzamiento, restaurar una copia en
un entorno aislado y verificar contratos, pagos y documentos descifrados.
Acordar explícitamente pérdida máxima de datos y tiempo máximo de recuperación.

Centralizar logs y alertar por respuestas 5xx, fallos de /health/, falta de
espacio y respaldos fallidos. No registrar cuerpos autenticados, claves o tokens.
Para volver a una imagen anterior, comprobar primero compatibilidad con las
migraciones aplicadas; una reversión de imagen no revierte la base de datos.

## Imagen Docker de producción

Construir con `docker build -f Dockerfile.production -t casarent:VERSION .`.
La imagen separa las dependencias de pruebas y excluye documentos privados.
Usar `.env.production.example` como lista de variables; los secretos vacíos deben
configurarse antes de iniciar. El archivo de CA indicado por PGSSLROOTCERT debe
montarse dentro del contenedor o reemplazarse por la ruta válida del proveedor.
La base PostgreSQL debe ser accesible con TLS verificable; esta imagen no crea
un servidor PostgreSQL ni certificados. Mantener Redis en red privada.

Tras elegir el alojamiento, quedan por definir el proxy HTTPS, DNS de Cloudflare,
almacenamiento persistente, PostgreSQL, Redis, respaldos y alertas. No apuntar el
dominio al servicio antes de validar todos los pasos anteriores.

## Servidor local mediante Cloudflare Tunnel

El entorno `compose.production.yml` usa esta máquina como servidor y mantiene
volúmenes separados de desarrollo y QA. PostgreSQL y Redis no publican puertos;
PostgreSQL usa TLS y Django verifica el certificado para el host `db`.
Nginx publica el puerto 4200 en loopback y sirve únicamente los medios públicos. Cloudflare Tunnel se
conecta a `http://gateway:8080` desde la red Docker `frontend`.

Los secretos están en `.env.production` (0600). El token del túnel se guarda en
`production-data/tunnel-token` (0600) y se monta como secreto Docker, sin incluirlo
en la imagen ni en los argumentos del proceso. `production-data/` está excluido
de Git y del contexto de construcción. No imprimir `docker compose config` sin
`--quiet`, porque contiene variables resueltas.

Para iniciar servicios existentes:

```
docker compose -f compose.production.yml up -d db redis web gateway
docker compose -f compose.production.yml --profile public up -d tunnel
```

Antes de una nueva versión, crear respaldo, aplicar migraciones y recoger estáticos
mediante un contenedor temporal con los mismos volúmenes:

```
python3 scripts/production-backup.py
docker compose -f compose.production.yml run --rm --entrypoint python web manage.py migrate --noinput
docker compose -f compose.production.yml run --rm --entrypoint python web manage.py collectstatic --noinput
```

La copia inicial procede de desarrollo; no se importaron los datos sintéticos de
QA. El archivo `production-data/backups/development-initial.dump` contiene la
copia inicial. Los respaldos contienen datos privados y deben guardarse cifrados
fuera de esta máquina. Para un punto coordinado entre base y archivos, pausar
escrituras mientras se realiza el respaldo. No eliminar los volúmenes.

La máquina debe permanecer encendida, conectada y sin suspensión; Docker Desktop
debe iniciarse después de reiniciar macOS. `restart: unless-stopped` recupera los
contenedores cuando Docker vuelve a funcionar. El certificado local de PostgreSQL
debe renovarse antes de un año, conservando su nombre DNS `db`.
