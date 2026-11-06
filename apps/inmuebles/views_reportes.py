from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from .models import Inmueble, Inquilino
from .services_reportes import (
    cartera_vencida,
    ingresos_mensuales,
    pagos_por_inquilino_e_inmueble,
    resumen_cartera_vencida,
)


@login_required
def dashboard(request):
    hoy = date.today()
    desde = request.GET.get("desde")
    hasta = request.GET.get("hasta")

    if desde:
        try:
            desde = date.fromisoformat(desde)
        except (ValueError, TypeError):
            desde = hoy.replace(day=1) - timedelta(days=365)
    else:
        desde = hoy.replace(day=1) - timedelta(days=365)

    if hasta:
        try:
            hasta = date.fromisoformat(hasta)
        except (ValueError, TypeError):
            hasta = hoy
    else:
        hasta = hoy

    inmueble_id = request.GET.get("inmueble") or None
    tipo_alquiler = request.GET.get("tipo_alquiler") or None
    estado_pago = request.GET.get("estado_pago") or None
    inquilino_id = request.GET.get("inquilino") or None
    inquilino_estado = request.GET.get("inquilino_estado") or None

    ingresos = ingresos_mensuales(request.cuenta, desde, hasta)
    vencidas = cartera_vencida(request.cuenta, desde, hasta)
    resumen = resumen_cartera_vencida(vencidas)
    pagos = pagos_por_inquilino_e_inmueble(request.cuenta, desde, hasta, inmueble_id, tipo_alquiler, estado_pago, inquilino_id, inquilino_estado)
    inmuebles = Inmueble.objects.filter(cuenta=request.cuenta).order_by("titulo")
    inquilinos = Inquilino.objects.filter(cuenta=request.cuenta).order_by("nombre_busqueda")

    hoy_local = date.today()
    for c in vencidas:
        c.dias_vencido = (hoy_local - c.fecha_vencimiento).days

    ingresos_json = [
        {"label": i["label"], "total": i["total"], "cantidad": i["cantidad"], "moneda": i["moneda"]}
        for i in ingresos
    ]

    ctx = {
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "ingresos": ingresos,
        "ingresos_json": ingresos_json,
        "vencidas": vencidas,
        "resumen": resumen,
        "pagos": pagos,
        "inmuebles": inmuebles,
        "inquilinos": inquilinos,
        "filtro_inmueble": inmueble_id or "",
        "filtro_tipo_alquiler": tipo_alquiler or "",
        "filtro_estado_pago": estado_pago or "",
        "filtro_inquilino": inquilino_id or "",
        "filtro_inquilino_estado": inquilino_estado or "",
    }
    return render(request, "inmuebles/dashboard.html", ctx)


@login_required
def exportar_pdf(request):
    hoy = date.today()
    desde = request.GET.get("desde")
    hasta = request.GET.get("hasta")

    if desde:
        try:
            desde = date.fromisoformat(desde)
        except (ValueError, TypeError):
            desde = hoy.replace(day=1) - timedelta(days=365)
    else:
        desde = hoy.replace(day=1) - timedelta(days=365)

    if hasta:
        try:
            hasta = date.fromisoformat(hasta)
        except (ValueError, TypeError):
            hasta = hoy
    else:
        hasta = hoy

    inmueble_id = request.GET.get("inmueble") or None
    tipo_alquiler = request.GET.get("tipo_alquiler") or None
    estado_pago = request.GET.get("estado_pago") or None
    inquilino_id = request.GET.get("inquilino") or None
    inquilino_estado = request.GET.get("inquilino_estado") or None

    ingresos = ingresos_mensuales(request.cuenta, desde, hasta)
    vencidas = cartera_vencida(request.cuenta, desde, hasta)
    resumen = resumen_cartera_vencida(vencidas)
    pagos = pagos_por_inquilino_e_inmueble(request.cuenta, desde, hasta, inmueble_id, tipo_alquiler, estado_pago, inquilino_id, inquilino_estado)

    hoy_local = date.today()
    for c in vencidas:
        c.dias_vencido = (hoy_local - c.fecha_vencimiento).days

    total_ingresos = {}
    for item in ingresos:
        total_ingresos[item["moneda"]] = total_ingresos.get(item["moneda"], 0) + item["total"]

    ctx = {
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "ingresos": ingresos,
        "totales_ingresos": sorted(total_ingresos.items()),
        "vencidas": vencidas,
        "resumen": resumen,
        "pagos": pagos,
    }
    html = render_to_string("inmuebles/dashboard_pdf.html", ctx)

    from xhtml2pdf import pisa
    result = HttpResponse(content_type="application/pdf")
    result["Content-Disposition"] = f'attachment; filename="dashboard_{desde}_{hasta}.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=result)
    if pisa_status.err:
        return HttpResponse("Error al generar PDF", status=500)
    return result
