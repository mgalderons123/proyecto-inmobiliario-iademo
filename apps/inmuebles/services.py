from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

import time

import requests
from django.conf import settings
from django.db import transaction

from .models import Contrato, Cuota, Inmueble, Inquilino, Pago, Propietario, Recibo
from django.db.models import Sum


def _lock_row(instance):
    """Reload current values under a row lock, preserving caller references.

    Call only inside transaction.atomic; all writers of an aggregate must lock
    its parent before checking balances, capacity or allocating sequence numbers.
    """
    locked = type(instance).objects.select_for_update().get(pk=instance.pk)
    for field in instance._meta.concrete_fields:
        setattr(instance, field.attname, getattr(locked, field.attname))
    instance._state.fields_cache.clear()
    return instance


class GeocodingError(Exception):
    pass


class InmuebleError(Exception):
    def __init__(self, field, message):
        self.field = field
        self.message = message
        super().__init__(message)


class ContratoError(Exception):
    def __init__(self, field, message):
        self.field = field
        self.message = message
        super().__init__(message)


class PropietarioError(Exception):
    def __init__(self, field, message):
        self.field = field
        self.message = message
        super().__init__(message)


class InquilinoError(Exception):
    def __init__(self, field, message):
        self.field = field
        self.message = message
        super().__init__(message)


class TenantLimitReached(InquilinoError):
    def __init__(self, account):
        self.account = account
        self.limit = account.limite_inquilinos
        super().__init__(
            None,
            f"Alcanzaste el límite de {self.limit} inquilinos del plan "
            f"{account.get_plan_display()}. Solicitá un cambio de plan para agregar otro.",
        )


class CuotaError(Exception):
    def __init__(self, field, message):
        self.field = field
        self.message = message
        super().__init__(message)


class PagoError(Exception):
    def __init__(self, field, message):
        self.field = field
        self.message = message
        super().__init__(message)


def geocode_address(direccion):
    time.sleep(1)
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": direccion, "format": "json", "limit": 1, "addressdetails": 1}
    headers = {"User-Agent": "PRY_INMOB/1.0 (admin@pryinmob.com)"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise GeocodingError(f"Error al geocodificar: {e}")

    if not data:
        raise GeocodingError("No se encontró la dirección. Verificá e intentá de nuevo.")

    result = data[0]
    lat = float(result["lat"])
    lon = float(result["lon"])
    display_name = result.get("display_name", direccion)
    return lat, lon, display_name


@transaction.atomic
def crear_inquilino(*, nombre, creado_por, cuenta=None, email="", telefono="", documento="", direccion="", notas=""):
    if not nombre:
        raise InquilinoError("nombre", "El nombre es obligatorio.")
    if cuenta is None:
        from apps.users.accounts import ensure_account_for_user
        cuenta = ensure_account_for_user(creado_por)
    from apps.users.models import Cuenta

    cuenta = Cuenta.objects.select_for_update().get(pk=cuenta.pk)
    if cuenta.inquilinos.count() >= cuenta.limite_inquilinos:
        raise TenantLimitReached(cuenta)
    return Inquilino.objects.create(
        nombre=nombre, email=email, telefono=telefono, documento=documento,
        direccion=direccion, notas=notas, creado_por=creado_por, cuenta=cuenta,
    )


@transaction.atomic
def actualizar_inquilino(inquilino, *, nombre=None, email=None, telefono=None, documento=None, direccion=None, notas=None):
    if nombre is not None:
        if not nombre:
            raise InquilinoError("nombre", "El nombre es obligatorio.")
        inquilino.nombre = nombre
    if email is not None:
        inquilino.email = email
    if telefono is not None:
        inquilino.telefono = telefono
    if documento is not None:
        inquilino.documento = documento
    if direccion is not None:
        inquilino.direccion = direccion
    if notas is not None:
        inquilino.notas = notas
    inquilino.save()
    return inquilino


def contratos_activos_inquilino(inquilino):
    from django.utils import timezone
    hoy = timezone.localdate()
    return inquilino.contratos.filter(
        estado=Contrato.Estado.ACTIVO,
    ).exclude(
        fecha_fin__lt=hoy,
    )


def contratos_vencidos_inquilino(inquilino):
    from django.utils import timezone
    hoy = timezone.localdate()
    activos_vencidos = inquilino.contratos.filter(
        estado=Contrato.Estado.ACTIVO,
        fecha_fin__lt=hoy,
    )
    finalizados = inquilino.contratos.filter(estado=Contrato.Estado.FINALIZADO)
    return (activos_vencidos | finalizados).distinct()


@transaction.atomic
def crear_propietario(*, nombre, creado_por, cuenta=None, email="", telefono="", documento="", direccion="", notas=""):
    if not nombre:
        raise PropietarioError("nombre", "El nombre es obligatorio.")
    if cuenta is None:
        from apps.users.accounts import ensure_account_for_user
        cuenta = ensure_account_for_user(creado_por)
    return Propietario.objects.create(
        nombre=nombre, email=email, telefono=telefono, documento=documento,
        direccion=direccion, notas=notas, creado_por=creado_por, cuenta=cuenta,
    )


@transaction.atomic
def actualizar_propietario(propietario, *, nombre=None, email=None, telefono=None, documento=None, direccion=None, notas=None):
    if nombre is not None:
        if not nombre:
            raise PropietarioError("nombre", "El nombre es obligatorio.")
        propietario.nombre = nombre
    if email is not None:
        propietario.email = email
    if telefono is not None:
        propietario.telefono = telefono
    if documento is not None:
        propietario.documento = documento
    if direccion is not None:
        propietario.direccion = direccion
    if notas is not None:
        propietario.notas = notas
    propietario.save()
    return propietario


def crear_inmueble(*, titulo, direccion, creado_por, cuenta=None, descripcion="", precio=None, moneda=None, tipo=Inmueble.Tipo.OTRO, estado=Inmueble.Estado.DISPONIBLE, propietario=None, superficie=None, habitaciones=None, banos=None, latitud=None, longitud=None):
    if not titulo:
        raise InmuebleError("titulo", "El título es obligatorio.")
    if not direccion:
        raise InmuebleError("direccion", "La dirección es obligatoria.")

    if latitud is not None and longitud is not None:
        lat, lon, direccion_norm = float(latitud), float(longitud), direccion
    else:
        try:
            lat, lon, direccion_norm = geocode_address(direccion)
        except GeocodingError:
            lat = lon = direccion_norm = None

    with transaction.atomic():
        if cuenta is None:
            from apps.users.accounts import ensure_account_for_user
            cuenta = ensure_account_for_user(creado_por)
        if propietario and propietario.cuenta_id != cuenta.id:
            raise InmuebleError("propietario", "El propietario no pertenece a esta cuenta.")
        return Inmueble.objects.create(
            titulo=titulo,
            direccion=direccion,
            direccion_normalizada=direccion_norm or "",
            descripcion=descripcion,
            precio=precio,
            moneda=moneda or cuenta.moneda_predeterminada,
            tipo=tipo,
            estado=estado,
            propietario=propietario,
            superficie=superficie,
            habitaciones=habitaciones,
            banos=banos,
            latitud=lat,
            longitud=lon,
            creado_por=creado_por,
            cuenta=cuenta,
        )


def actualizar_inmueble(inmueble, *, titulo=None, direccion=None, descripcion=None, precio=None, moneda=None, tipo=None, estado=None, propietario=None, superficie=None, habitaciones=None, banos=None, tipo_alquiler=None, latitud=None, longitud=None):
    if titulo is not None:
        if not titulo:
            raise InmuebleError("titulo", "El título es obligatorio.")
        inmueble.titulo = titulo

    if direccion is not None:
        if not direccion:
            raise InmuebleError("direccion", "La dirección es obligatoria.")
        inmueble.direccion = direccion
        if latitud is not None and longitud is not None:
            inmueble.latitud = float(latitud)
            inmueble.longitud = float(longitud)
            inmueble.direccion_normalizada = direccion
        else:
            try:
                lat, lon, direccion_norm = geocode_address(direccion)
            except GeocodingError:
                lat = lon = direccion_norm = None
            inmueble.latitud = lat
            inmueble.longitud = lon
            inmueble.direccion_normalizada = direccion_norm or ""

    if descripcion is not None:
        inmueble.descripcion = descripcion
    if precio is not None:
        inmueble.precio = precio
    if moneda is not None:
        inmueble.moneda = moneda
    if tipo is not None:
        inmueble.tipo = tipo
    if estado is not None:
        inmueble.estado = estado
    if propietario is not None:
        if propietario.cuenta_id != inmueble.cuenta_id:
            raise InmuebleError("propietario", "El propietario no pertenece a esta cuenta.")
        inmueble.propietario = propietario
    if superficie is not None:
        inmueble.superficie = superficie
    if habitaciones is not None:
        inmueble.habitaciones = habitaciones
    if banos is not None:
        inmueble.banos = banos
    if tipo_alquiler is not None:
        inmueble.tipo_alquiler = tipo_alquiler

    inmueble.save()
    return inmueble


def inmuebles_disponibles(cuenta=None):
    qs = Inmueble.objects.filter(estado=Inmueble.Estado.DISPONIBLE)
    return qs.filter(cuenta=cuenta) if cuenta else qs


@transaction.atomic
def crear_contrato(*, inmueble, tipo, creado_por, inquilino=None, inquilino_registrado=None, inquilino_nombre="", inquilino_email="", inquilino_telefono="", frecuencia_pago=Contrato.FrecuenciaPago.MENSUAL, duracion_anos=None, fecha_inicio, fecha_fin=None, monto, moneda=None, comision=None, garantia=None):
    if not inmueble:
        raise ContratoError("inmueble", "El inmueble es obligatorio.")

    _lock_row(inmueble)
    no_disponibles = (Inmueble.Estado.ALQUILADO, Inmueble.Estado.VENDIDO)
    if tipo in (Contrato.Tipo.VENTA, Contrato.Tipo.AUTORIZACION_VENTA) and inmueble.estado in no_disponibles:
        raise ContratoError("inmueble", "El inmueble no está disponible para venta.")

    if tipo == Contrato.Tipo.ALQUILER:
        if not inquilino_registrado:
            legacy_name = inquilino_nombre
            if not legacy_name and inquilino:
                legacy_name = inquilino.get_full_name() or inquilino.username
            if not legacy_name:
                raise ContratoError(
                    "inquilino_registrado",
                    "Los contratos de alquiler requieren un inquilino registrado.",
                )
            if inquilino:
                inquilino_registrado = Inquilino.objects.filter(
                    cuenta=inmueble.cuenta,
                    user=inquilino,
                ).first()
            if not inquilino_registrado:
                inquilino_registrado = crear_inquilino(
                    nombre=legacy_name,
                    email=inquilino_email or (inquilino.email if inquilino else ""),
                    telefono=inquilino_telefono,
                    creado_por=creado_por,
                    cuenta=inmueble.cuenta,
                )
            if inquilino and not inquilino_registrado.user_id:
                inquilino_registrado.user = inquilino
                inquilino_registrado.save(update_fields=["user"])
        if inmueble.tipo_alquiler == Inmueble.TipoAlquiler.POR_HABITACIONES:
            if not inmueble.habitaciones or inmueble.habitaciones < 1:
                raise ContratoError("inmueble", "Para alquiler por habitaciones debe especificar la cantidad de habitaciones.")
            activos = inmueble.contratos.filter(tipo=Contrato.Tipo.ALQUILER, estado=Contrato.Estado.ACTIVO).count()
            if activos >= inmueble.habitaciones:
                raise ContratoError("inmueble", f"Ya se alcanzó el máximo de {inmueble.habitaciones} contratos de alquiler.")
        else:
            # COMPLETA o POR_LOCAL: un solo contrato activo
            if inmueble.estado in no_disponibles:
                raise ContratoError("inmueble", "El inmueble no está disponible para alquiler.")
            if inmueble.contratos.filter(tipo=Contrato.Tipo.ALQUILER, estado=Contrato.Estado.ACTIVO).exists():
                raise ContratoError("inmueble", "Este inmueble ya tiene un contrato de alquiler activo.")

    if not inquilino and not inquilino_registrado and not inquilino_nombre:
        raise ContratoError("inquilino_nombre", "Debe especificar un inquilino, un inquilino registrado o el nombre de la persona.")

    if inquilino_registrado and inquilino_registrado.cuenta_id != inmueble.cuenta_id:
        raise ContratoError("inquilino_registrado", "El inquilino no pertenece a esta cuenta.")

    if not monto or monto <= 0:
        raise ContratoError("monto", "El monto debe ser mayor a cero.")

    if tipo == Contrato.Tipo.ALQUILER and fecha_fin and fecha_fin < fecha_inicio:
        raise ContratoError("fecha_fin", "La fecha de fin no puede ser anterior a la fecha de inicio.")

    contrato = Contrato.objects.create(
        inmueble=inmueble,
        tipo=tipo,
        inquilino=inquilino,
        inquilino_registrado=inquilino_registrado,
        inquilino_nombre=inquilino_nombre if not inquilino and not inquilino_registrado else "",
        inquilino_email=inquilino_email if not inquilino and not inquilino_registrado else "",
        inquilino_telefono=inquilino_telefono if not inquilino and not inquilino_registrado else "",
        frecuencia_pago=frecuencia_pago,
        duracion_anos=duracion_anos,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        monto=monto,
        moneda=moneda or inmueble.moneda,
        comision=comision,
        garantia=garantia,
        creado_por=creado_por,
    )

    if tipo == Contrato.Tipo.ALQUILER:
        if inmueble.tipo_alquiler == Inmueble.TipoAlquiler.POR_HABITACIONES:
            activos = inmueble.contratos.filter(tipo=Contrato.Tipo.ALQUILER, estado=Contrato.Estado.ACTIVO).count()
            nuevo_estado = Inmueble.Estado.ALQUILADO if activos >= inmueble.habitaciones else Inmueble.Estado.DISPONIBLE
        else:
            nuevo_estado = Inmueble.Estado.ALQUILADO
    elif tipo == Contrato.Tipo.AUTORIZACION_VENTA:
        nuevo_estado = Inmueble.Estado.RESERVADO
    else:
        nuevo_estado = Inmueble.Estado.VENDIDO
    inmueble.estado = nuevo_estado
    inmueble.save(update_fields=["estado"])

    return contrato


@transaction.atomic
def actualizar_contrato(contrato, *, tipo=None, inquilino=None, inquilino_registrado=None,
                        inquilino_nombre=None, inquilino_email=None, inquilino_telefono=None,
                        frecuencia_pago=None, duracion_anos=None,
                        fecha_inicio=None, fecha_fin=None, monto=None, moneda=None, comision=None, garantia=None):
    if tipo is not None:
        contrato.tipo = tipo
    if inquilino is not None:
        contrato.inquilino = inquilino
    if inquilino_registrado is not None:
        if inquilino_registrado.cuenta_id != contrato.inmueble.cuenta_id:
            raise ContratoError("inquilino_registrado", "El inquilino no pertenece a esta cuenta.")
        contrato.inquilino_registrado = inquilino_registrado
    if inquilino_nombre is not None:
        contrato.inquilino_nombre = inquilino_nombre
    if inquilino_email is not None:
        contrato.inquilino_email = inquilino_email
    if inquilino_telefono is not None:
        contrato.inquilino_telefono = inquilino_telefono
    if contrato.tipo == Contrato.Tipo.ALQUILER and not contrato.inquilino_registrado:
        raise ContratoError(
            "inquilino_registrado",
            "Los contratos de alquiler requieren un inquilino registrado.",
        )
    if frecuencia_pago is not None:
        contrato.frecuencia_pago = frecuencia_pago
    if duracion_anos is not None:
        contrato.duracion_anos = duracion_anos
    if fecha_inicio is not None:
        contrato.fecha_inicio = fecha_inicio
    if fecha_fin is not None:
        contrato.fecha_fin = fecha_fin
    if fecha_inicio is not None and fecha_fin is not None and fecha_fin < fecha_inicio:
        raise ContratoError("fecha_fin", "La fecha de fin no puede ser anterior a la fecha de inicio.")
    if monto is not None:
        if monto <= 0:
            raise ContratoError("monto", "El monto debe ser mayor a cero.")
        contrato.monto = monto
    if moneda is not None and moneda != contrato.moneda:
        if contrato.cuotas.exists():
            raise ContratoError("moneda", "No se puede cambiar la moneda de un contrato con cuotas.")
        contrato.moneda = moneda
    if comision is not None:
        contrato.comision = comision
    if garantia is not None:
        contrato.garantia = garantia
    contrato.save()
    return contrato


@transaction.atomic
def renovar_contrato(contrato_actual, *, fecha_inicio, fecha_fin, monto, moneda=None, comision=None):
    _lock_row(contrato_actual.inmueble)
    _lock_row(contrato_actual)
    if contrato_actual.estado != Contrato.Estado.ACTIVO:
        raise ContratoError("estado", "Solo se puede renovar un contrato activo.")
    if monto <= 0:
        raise ContratoError("monto", "El monto debe ser mayor a cero.")
    if fecha_fin and fecha_fin < fecha_inicio:
        raise ContratoError("fecha_fin", "La fecha de fin no puede ser anterior a la fecha de inicio.")

    nuevo = Contrato.objects.create(
        inmueble=contrato_actual.inmueble,
        tipo=contrato_actual.tipo,
        inquilino=contrato_actual.inquilino,
        inquilino_registrado=contrato_actual.inquilino_registrado,
        inquilino_nombre=contrato_actual.inquilino_nombre,
        inquilino_email=contrato_actual.inquilino_email,
        inquilino_telefono=contrato_actual.inquilino_telefono,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        monto=monto,
        moneda=moneda or contrato_actual.moneda,
        comision=comision,
        creado_por=contrato_actual.creado_por,
    )

    contrato_actual.estado = Contrato.Estado.FINALIZADO
    contrato_actual.fecha_finalizacion = date.today()
    contrato_actual.save(update_fields=["estado", "fecha_finalizacion"])
    return nuevo


def _actualizar_estado_inmueble_tras_fin(contrato):
    inmueble = contrato.inmueble
    activos = inmueble.contratos.filter(estado=Contrato.Estado.ACTIVO).exclude(pk=contrato.pk).count()
    if activos == 0:
        inmueble.estado = Inmueble.Estado.DISPONIBLE
        inmueble.save(update_fields=["estado"])
    elif inmueble.tipo_alquiler == Inmueble.TipoAlquiler.POR_HABITACIONES and activos < inmueble.habitaciones:
        inmueble.estado = Inmueble.Estado.DISPONIBLE
        inmueble.save(update_fields=["estado"])


@transaction.atomic
def rescindir_contrato(contrato):
    _lock_row(contrato.inmueble)
    _lock_row(contrato)
    if contrato.estado != Contrato.Estado.ACTIVO:
        raise ContratoError("estado", "Solo se puede rescindir un contrato activo.")
    contrato.estado = Contrato.Estado.RESCINDIDO
    contrato.fecha_finalizacion = date.today()
    contrato.save(update_fields=["estado", "fecha_finalizacion"])

    _actualizar_estado_inmueble_tras_fin(contrato)
    return contrato


@transaction.atomic
def finalizar_contrato(contrato):
    _lock_row(contrato.inmueble)
    _lock_row(contrato)
    if contrato.estado != Contrato.Estado.ACTIVO:
        raise ContratoError("estado", "Solo se puede finalizar un contrato activo.")
    contrato.estado = Contrato.Estado.FINALIZADO
    contrato.fecha_finalizacion = date.today()
    contrato.save(update_fields=["estado", "fecha_finalizacion"])

    _actualizar_estado_inmueble_tras_fin(contrato)

    return contrato


# ---------------------------------------------------------------------------
# Cobros
# ---------------------------------------------------------------------------

def actualizar_estado_cuota(cuota):
    """Actualiza el estado de una cuota según pagos y fecha de vencimiento."""
    total_pagado = cuota.pagos.filter(estado=Pago.Estado.APROBADO).aggregate(total=Sum("monto"))["total"] or 0
    if total_pagado <= 0:
        if date.today() > cuota.fecha_vencimiento + timedelta(days=5):
            cuota.estado = Cuota.Estado.VENCIDO
        else:
            cuota.estado = Cuota.Estado.PENDIENTE
        cuota.fecha_pago = None
    elif total_pagado >= cuota.total:
        cuota.estado = Cuota.Estado.PAGADO
        cuota.fecha_pago = date.today()
    else:
        cuota.estado = Cuota.Estado.PARCIAL
        cuota.fecha_pago = None
    cuota.save(update_fields=["estado", "fecha_pago"])
    return cuota


def ultimo_numero_cuota(contrato):
    """Retorna el último número de cuota para un contrato, o 0 si no hay."""
    ultima = contrato.cuotas.order_by("numero").last()
    return ultima.numero if ultima else 0


@transaction.atomic
def generar_cuota_mensual(*, contrato, creado_por):
    """Genera la próxima cuota mensual para un contrato de alquiler."""
    _lock_row(contrato)
    if contrato.tipo != Contrato.Tipo.ALQUILER:
        raise CuotaError("contrato", "Solo se pueden generar cuotas mensuales para contratos de alquiler.")
    if contrato.estado != Contrato.Estado.ACTIVO:
        raise CuotaError("contrato", "El contrato no está activo.")

    hoy = date.today()
    ultima = contrato.cuotas.order_by("numero").last()
    if ultima and ultima.fecha_vencimiento <= hoy and ultima.estado not in (Cuota.Estado.PAGADO,):
        raise CuotaError("contrato", "La cuota anterior aún no está pagada. Regularizala antes de generar la siguiente.")

    nuevo_numero = ultimo_numero_cuota(contrato) + 1

    if ultima:
        if ultima.fecha_vencimiento.month == 12:
            mes_siguiente = 1
            anio_siguiente = ultima.fecha_vencimiento.year + 1
        else:
            mes_siguiente = ultima.fecha_vencimiento.month + 1
            anio_siguiente = ultima.fecha_vencimiento.year
    else:
        if hoy.month == 12:
            mes_siguiente = 1
            anio_siguiente = hoy.year + 1
        else:
            mes_siguiente = hoy.month + 1
            anio_siguiente = hoy.year

    if contrato.cuotas.filter(
        fecha_vencimiento__year=anio_siguiente,
        fecha_vencimiento__month=mes_siguiente,
    ).exists():
        raise CuotaError("contrato", "Ya existe una cuota para ese período.")

    fecha_vencimiento = date(anio_siguiente, mes_siguiente, 1)
    meses_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                 "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

    cuota = Cuota.objects.create(
        contrato=contrato,
        numero=nuevo_numero,
        descripcion=f"Cuota {nuevo_numero} - {meses_es[mes_siguiente - 1].capitalize()} {anio_siguiente}",
        fecha_vencimiento=fecha_vencimiento,
        monto=contrato.monto,
    )
    return cuota


@transaction.atomic
def crear_cuota_personalizada(*, contrato, monto, descripcion, fecha_vencimiento, creado_por):
    """Crea una cuota personalizada (para contratos de venta)."""
    if not monto or monto <= 0:
        raise CuotaError("monto", "El monto debe ser mayor a cero.")
    if not descripcion:
        raise CuotaError("descripcion", "La descripción es obligatoria.")
    if not fecha_vencimiento:
        raise CuotaError("fecha_vencimiento", "La fecha de vencimiento es obligatoria.")

    _lock_row(contrato)
    nuevo_numero = ultimo_numero_cuota(contrato) + 1
    cuota = Cuota.objects.create(
        contrato=contrato,
        numero=nuevo_numero,
        descripcion=descripcion,
        fecha_vencimiento=fecha_vencimiento,
        monto=monto,
    )
    return cuota


@transaction.atomic
def actualizar_cuota(cuota, *, descripcion=None, monto=None, fecha_vencimiento=None):
    _lock_row(cuota)
    if cuota.estado == Cuota.Estado.PAGADO:
        raise CuotaError("cuota", "No se puede modificar una cuota ya pagada.")
    if descripcion is not None:
        if not descripcion:
            raise CuotaError("descripcion", "La descripción es obligatoria.")
        cuota.descripcion = descripcion
    if monto is not None:
        if monto <= 0:
            raise CuotaError("monto", "El monto debe ser mayor a cero.")
        cuota.monto = monto
    if fecha_vencimiento is not None:
        cuota.fecha_vencimiento = fecha_vencimiento
    cuota.save()
    return cuota


@transaction.atomic
def registrar_pago(*, cuota, monto, fecha_pago, metodo_pago, creado_por, archivo_comprobante=None, comprobante="", observaciones=""):
    """Registra un pago contra una cuota en estado pendiente."""
    _lock_row(cuota)
    if not monto or monto <= 0:
        raise PagoError("monto", "El monto debe ser mayor a cero.")

    if cuota.estado == Cuota.Estado.PAGADO:
        raise PagoError("cuota", "No se puede registrar un pago contra una cuota ya pagada.")

    total_pagado = cuota.pagos.exclude(estado=Pago.Estado.RECHAZADO).aggregate(total=Sum("monto"))["total"] or 0
    if total_pagado + monto > cuota.total:
        raise PagoError("monto", f"El monto excede el saldo pendiente de {cuota.moneda} {cuota.total - total_pagado:.2f}.")

    pago = Pago.objects.create(
        cuota=cuota,
        monto=monto,
        fecha_pago=fecha_pago,
        metodo_pago=metodo_pago,
        estado=Pago.Estado.PENDIENTE,
        archivo_comprobante=archivo_comprobante,
        comprobante=comprobante,
        observaciones=observaciones,
        creado_por=creado_por,
    )
    return pago


@transaction.atomic
def aprobar_pago(pago):
    """Aprueba un pago, actualiza la cuota y genera el recibo."""
    _lock_row(pago.cuota)
    pago = Pago.objects.select_for_update().get(pk=pago.pk)
    if pago.estado != Pago.Estado.PENDIENTE:
        raise PagoError("estado", "Solo se pueden aprobar pagos pendientes.")

    pago.estado = Pago.Estado.APROBADO
    pago.fecha_aprobacion = date.today()
    pago.save(update_fields=["estado", "fecha_aprobacion"])

    actualizar_estado_cuota(pago.cuota)

    generar_recibo(pago)
    return pago


@transaction.atomic
def rechazar_pago(pago, *, motivo):
    """Rechaza un pago con motivo obligatorio."""
    _lock_row(pago.cuota)
    pago = Pago.objects.select_for_update().get(pk=pago.pk)
    if pago.estado != Pago.Estado.PENDIENTE:
        raise PagoError("estado", "Solo se pueden rechazar pagos pendientes.")
    if not motivo:
        raise PagoError("motivo_rechazo", "Debe indicar un motivo para rechazar el pago.")

    pago.estado = Pago.Estado.RECHAZADO
    pago.motivo_rechazo = motivo
    pago.save(update_fields=["estado", "motivo_rechazo"])
    return pago


def generar_recibo(pago):
    from django.utils.crypto import get_random_string
    codigo = f"REC-{pago.pk:05d}-{get_random_string(6).upper()}"
    recibo, created = Recibo.objects.get_or_create(pago=pago, defaults={"codigo": codigo})
    return recibo


@transaction.atomic
def aplicar_multa(*, cuota, monto_fijo=None, porcentaje=None, motivo=""):
    """Aplica una multa a una cuota vencida. Acepta monto fijo o porcentaje."""
    _lock_row(cuota)
    if cuota.estado in (Cuota.Estado.PAGADO,):
        raise CuotaError("cuota", "No se puede aplicar multa a una cuota ya pagada.")

    if monto_fijo is not None and monto_fijo > 0:
        multa = monto_fijo
    elif porcentaje is not None and porcentaje > 0:
        multa = (cuota.monto * Decimal(str(porcentaje)) / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    else:
        raise CuotaError("multa", "Debe indicar un monto fijo o un porcentaje.")

    Cuota.objects.filter(pk=cuota.pk).update(monto_multa=cuota.monto_multa + multa)
    cuota.refresh_from_db()
    return cuota


def calcular_saldo_contrato(contrato):
    """Calcula el saldo total pendiente de un contrato."""
    total_pagado = Pago.objects.filter(
        cuota__contrato=contrato, estado=Pago.Estado.APROBADO
    ).aggregate(total=Sum("monto"))["total"] or 0
    total_cuotas = contrato.cuotas.aggregate(
        total=Sum("monto") + Sum("monto_multa")
    )["total"] or 0
    return total_cuotas - total_pagado


# ---------------------------------------------------------------------------
# Carga masiva desde Excel
# ---------------------------------------------------------------------------

import io
import re

from openpyxl import load_workbook


def _safe_str(val):
    if val is None:
        return ""
    return str(val).strip()


def _safe_decimal(val):
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val):
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _validate_email(email):
    if not email:
        return True
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def _validate_choice(value, choices):
    if choices and isinstance(choices[0], tuple):
        valid = [c[0] for c in choices]
    else:
        valid = list(choices)
    return value in valid


def _procesar_inquilinos(ws, usuario, cuenta):
    errores = []
    advertencias = []
    creados = 0
    headers = [_safe_str(c.value).lower() for c in ws[1]]
    campos_requeridos = ["nombre"]
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if all(v is None for v in row):
            continue
        data = dict(zip(headers, row))
        nombre = _safe_str(data.get("nombre"))
        if not nombre:
            errores.append({"hoja": "Inquilinos", "fila": idx, "campo": "nombre", "mensaje": "El nombre es obligatorio.", "importancia": "alta"})
            continue
        email = _safe_str(data.get("email", ""))
        if email and not _validate_email(email):
            errores.append({"hoja": "Inquilinos", "fila": idx, "campo": "email", "mensaje": f"Email inválido: '{email}'", "importancia": "alta"})
            continue
        try:
            crear_inquilino(
                nombre=nombre,
                creado_por=usuario,
                cuenta=cuenta,
                email=email,
                telefono=_safe_str(data.get("telefono", "")),
                documento=_safe_str(data.get("documento", "")),
                direccion=_safe_str(data.get("direccion", "")),
                notas=_safe_str(data.get("notas", "")),
            )
            creados += 1
        except InquilinoError as e:
            errores.append({"hoja": "Inquilinos", "fila": idx, "campo": e.field, "mensaje": e.message, "importancia": "alta"})
    return {"creados": creados, "errores": len(errores), "detalle_errores": errores, "detalle_advertencias": advertencias}


def _procesar_propietarios(ws, usuario, cuenta):
    errores = []
    advertencias = []
    creados = 0
    headers = [_safe_str(c.value).lower() for c in ws[1]]
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if all(v is None for v in row):
            continue
        data = dict(zip(headers, row))
        nombre = _safe_str(data.get("nombre"))
        if not nombre:
            errores.append({"hoja": "Propietarios", "fila": idx, "campo": "nombre", "mensaje": "El nombre es obligatorio.", "importancia": "alta"})
            continue
        email = _safe_str(data.get("email", ""))
        if email and not _validate_email(email):
            errores.append({"hoja": "Propietarios", "fila": idx, "campo": "email", "mensaje": f"Email inválido: '{email}'", "importancia": "alta"})
            continue
        try:
            crear_propietario(
                nombre=nombre,
                creado_por=usuario,
                cuenta=cuenta,
                email=email,
                telefono=_safe_str(data.get("telefono", "")),
                documento=_safe_str(data.get("documento", "")),
                direccion=_safe_str(data.get("direccion", "")),
                notas=_safe_str(data.get("notas", "")),
            )
            creados += 1
        except PropietarioError as e:
            errores.append({"hoja": "Propietarios", "fila": idx, "campo": e.field, "mensaje": e.message, "importancia": "alta"})
    return {"creados": creados, "errores": len(errores), "detalle_errores": errores, "detalle_advertencias": advertencias}


def _procesar_inmuebles(ws, usuario, cuenta):
    errores = []
    advertencias = []
    creados = 0
    headers = [_safe_str(c.value).lower() for c in ws[1]]
    tipos_validos = [c[0] for c in Inmueble.Tipo.choices]
    estados_validos = [c[0] for c in Inmueble.Estado.choices]
    tipos_alquiler_validos = [c[0] for c in Inmueble.TipoAlquiler.choices]
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if all(v is None for v in row):
            continue
        data = dict(zip(headers, row))
        titulo = _safe_str(data.get("titulo"))
        direccion = _safe_str(data.get("direccion"))
        if not titulo:
            errores.append({"hoja": "Inmuebles", "fila": idx, "campo": "titulo", "mensaje": "El título es obligatorio.", "importancia": "alta"})
            continue
        if not direccion:
            errores.append({"hoja": "Inmuebles", "fila": idx, "campo": "direccion", "mensaje": "La dirección es obligatoria.", "importancia": "alta"})
            continue
        tipo = _safe_str(data.get("tipo", "otro")).lower()
        if tipo and not _validate_choice(tipo, tipos_validos):
            errores.append({"hoja": "Inmuebles", "fila": idx, "campo": "tipo", "mensaje": f"Tipo inválido: '{tipo}'. Opciones: {', '.join(tipos_validos)}", "importancia": "alta"})
            continue
        estado = _safe_str(data.get("estado", "disponible")).lower()
        if estado and not _validate_choice(estado, estados_validos):
            errores.append({"hoja": "Inmuebles", "fila": idx, "campo": "estado", "mensaje": f"Estado inválido: '{estado}'. Opciones: {', '.join(estados_validos)}", "importancia": "alta"})
            continue
        tipo_alquiler = _safe_str(data.get("tipo_alquiler", "completa")).lower()
        if tipo_alquiler and not _validate_choice(tipo_alquiler, tipos_alquiler_validos):
            errores.append({"hoja": "Inmuebles", "fila": idx, "campo": "tipo_alquiler", "mensaje": f"Tipo de alquiler inválido: '{tipo_alquiler}'. Opciones: {', '.join(tipos_alquiler_validos)}", "importancia": "alta"})
            continue
        propietario = None
        doc_prop = _safe_str(data.get("propietario_documento", ""))
        if doc_prop:
            propietario = next(
                (
                    item
                    for item in Propietario.objects.filter(cuenta=cuenta)
                    if item.documento == doc_prop
                ),
                None,
            )
            if not propietario:
                advertencias.append({"hoja": "Inmuebles", "fila": idx, "campo": "propietario_documento", "mensaje": f"No se encontró propietario con documento '{doc_prop}'. Se creará sin propietario.", "importancia": "baja"})
        precio = _safe_decimal(data.get("precio"))
        if precio is not None and precio < 0:
            errores.append({"hoja": "Inmuebles", "fila": idx, "campo": "precio", "mensaje": "El precio no puede ser negativo.", "importancia": "alta"})
            continue
        superficie = _safe_decimal(data.get("superficie"))
        habitaciones = _safe_int(data.get("habitaciones"))
        banos = _safe_int(data.get("banos"))
        try:
            crear_inmueble(
                titulo=titulo,
                direccion=direccion,
                creado_por=usuario,
                cuenta=cuenta,
                descripcion=_safe_str(data.get("descripcion", "")),
                precio=precio,
                tipo=tipo or Inmueble.Tipo.OTRO,
                estado=estado or Inmueble.Estado.DISPONIBLE,
                propietario=propietario,
                superficie=superficie,
                habitaciones=habitaciones,
                banos=banos,
            )
            creados += 1
        except InmuebleError as e:
            errores.append({"hoja": "Inmuebles", "fila": idx, "campo": e.field, "mensaje": e.message, "importancia": "alta"})
    return {"creados": creados, "errores": len(errores), "detalle_errores": errores, "detalle_advertencias": advertencias}


def cargar_datos_desde_excel(usuario, archivo, cuenta=None):
    """Procesa un archivo Excel con hojas Inquilinos, Propietarios e Inmuebles."""
    if cuenta is None:
        from apps.users.accounts import ensure_account_for_user

        cuenta = ensure_account_for_user(usuario)
    try:
        wb = load_workbook(archivo, read_only=True, data_only=True)
    except Exception:
        return {
            "valido": False,
            "mensaje": "El archivo no es un archivo Excel válido.",
            "resumen": {},
            "errores": [],
            "advertencias": [],
        }
    resumen = {}
    todos_errores = []
    todas_advertencias = []
    mapa_hojas = {
        "Inquilinos": _procesar_inquilinos,
        "Propietarios": _procesar_propietarios,
        "Inmuebles": _procesar_inmuebles,
    }
    for nombre_hoja, func in mapa_hojas.items():
        if nombre_hoja in wb.sheetnames:
            ws = wb[nombre_hoja]
            resultado = func(ws, usuario, cuenta)
            resumen[nombre_hoja.lower()] = {"creados": resultado["creados"], "errores": resultado["errores"]}
            todos_errores.extend(resultado["detalle_errores"])
            todas_advertencias.extend(resultado["detalle_advertencias"])
        else:
            advertencias.append({"hoja": nombre_hoja, "fila": 0, "campo": "-", "mensaje": f"La hoja '{nombre_hoja}' no existe en el archivo.", "importancia": "baja"})
    total_creados = sum(r["creados"] for r in resumen.values())
    total_errores = len(todos_errores)
    return {
        "valido": total_errores == 0,
        "resumen": resumen,
        "errores": todos_errores,
        "advertencias": todas_advertencias,
        "total_creados": total_creados,
        "total_errores": total_errores,
    }
