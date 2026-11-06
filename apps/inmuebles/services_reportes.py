from datetime import date, timedelta

from django.db.models import Count, Sum
from django.db.models.functions import ExtractMonth, ExtractYear

from .models import Contrato, Cuota, Inquilino, Pago


def _account_id(subject):
    if hasattr(subject, "moneda_predeterminada"):
        return subject.pk
    from apps.users.accounts import ensure_account_for_user

    return ensure_account_for_user(subject).pk


def ingresos_mensuales(cuenta, desde, hasta):
    account_id = _account_id(cuenta)
    pagos = (
        Pago.objects.filter(
            cuota__contrato__inmueble__cuenta_id=account_id,
            estado=Pago.Estado.APROBADO,
            fecha_pago__gte=desde,
            fecha_pago__lte=hasta,
        )
        .annotate(anio=ExtractYear("fecha_pago"), mes=ExtractMonth("fecha_pago"))
        .values("anio", "mes", "cuota__contrato__moneda")
        .annotate(total=Sum("monto"), cantidad=Count("id"))
        .order_by("anio", "mes")
    )
    meses_es = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]
    result = []
    for item in pagos:
        result.append({
            "anio": item["anio"],
            "mes": item["mes"],
            "label": f"{meses_es[item['mes'] - 1]} {item['anio']}",
            "total": float(item["total"]),
            "cantidad": item["cantidad"],
            "moneda": item["cuota__contrato__moneda"],
        })
    return result


def cartera_vencida(cuenta, desde, hasta):
    account_id = _account_id(cuenta)
    return list(
        Cuota.objects.filter(
            contrato__inmueble__cuenta_id=account_id,
            estado__in=[Cuota.Estado.PENDIENTE, Cuota.Estado.VENCIDO, Cuota.Estado.PARCIAL],
            fecha_vencimiento__gte=desde,
            fecha_vencimiento__lte=hasta,
        )
        .select_related("contrato", "contrato__inmueble")
        .prefetch_related("contrato__inquilino_registrado")
        .order_by("fecha_vencimiento")
    )


def pagos_por_inquilino_e_inmueble(cuenta, desde, hasta, inmueble_id=None, tipo_alquiler=None, estado_pago=None, inquilino_id=None, inquilino_estado=None):
    account_id = _account_id(cuenta)
    qs = (
        Pago.objects.filter(
            cuota__contrato__inmueble__cuenta_id=account_id,
            fecha_pago__gte=desde,
            fecha_pago__lte=hasta,
        )
        .select_related(
            "cuota",
            "cuota__contrato",
            "cuota__contrato__inmueble",
            "cuota__contrato__inquilino_registrado",
        )
        .order_by("cuota__contrato__inmueble__titulo")
    )

    if estado_pago and estado_pago != "todos":
        qs = qs.filter(estado=estado_pago)

    if inmueble_id:
        qs = qs.filter(cuota__contrato__inmueble_id=inmueble_id)

    if tipo_alquiler:
        qs = qs.filter(cuota__contrato__inmueble__tipo_alquiler=tipo_alquiler)

    if inquilino_id:
        qs = qs.filter(cuota__contrato__inquilino_registrado_id=inquilino_id)

    if inquilino_estado == "activo":
        qs = qs.filter(cuota__contrato__estado=Contrato.Estado.ACTIVO)
    elif inquilino_estado == "no_activo":
        qs = qs.exclude(cuota__contrato__estado=Contrato.Estado.ACTIVO)

    result = []
    for p in qs:
        contrato = p.cuota.contrato
        inquilino = (
            contrato.inquilino_registrado.nombre
            if contrato.inquilino_registrado
            else contrato.inquilino_nombre or "—"
        )
        result.append({
            "inquilino": inquilino,
            "inmueble": contrato.inmueble.titulo,
            "cuota_numero": p.cuota.numero,
            "cuota_descripcion": p.cuota.descripcion,
            "vencimiento": p.cuota.fecha_vencimiento,
            "monto": float(p.monto),
            "moneda": contrato.moneda,
            "fecha_pago": p.fecha_pago,
            "metodo_pago": p.get_metodo_pago_display(),
            "estado_pago": p.get_estado_display(),
            "recibo_codigo": getattr(getattr(p, "recibo", None), "codigo", None),
        })
    return result


def resumen_cartera_vencida(cuotas):
    if not cuotas:
        return {
            "total_adeudado": 0,
            "totales_adeudados": [],
            "cantidad_cuotas": 0,
            "cantidad_contratos": 0,
            "dias_maximo": 0,
        }
    hoy = date.today()
    totals = {}
    for cuota in cuotas:
        totals[cuota.moneda] = totals.get(cuota.moneda, 0) + cuota.total
    contratos = set(c.contrato_id for c in cuotas)
    vencidos = [c for c in cuotas if c.fecha_vencimiento <= hoy]
    dias_max = max((hoy - c.fecha_vencimiento).days for c in vencidos) if vencidos else 0
    return {
        "total_adeudado": round(float(next(iter(totals.values()))), 2) if len(totals) == 1 else None,
        "totales_adeudados": [
            {"moneda": currency, "total": amount}
            for currency, amount in sorted(totals.items())
        ],
        "cantidad_cuotas": len(cuotas),
        "cantidad_contratos": len(contratos),
        "dias_maximo": dias_max,
    }
