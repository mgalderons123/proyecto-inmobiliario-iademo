from datetime import date, timedelta
import io
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string

from apps.inmuebles.services import (
    ContratoError,
    CuotaError,
    InmuebleError,
    InquilinoError,
    PagoError,
    PropietarioError,
    actualizar_contrato,
    actualizar_cuota,
    actualizar_estado_cuota,
    actualizar_inmueble,
    actualizar_inquilino,
    actualizar_propietario,
    aplicar_multa,
    aprobar_pago,
    cargar_datos_desde_excel,
    contratos_activos_inquilino,
    contratos_vencidos_inquilino,
    crear_contrato,
    crear_cuota_personalizada,
    crear_inmueble,
    crear_inquilino,
    crear_propietario,
    finalizar_contrato,
    generar_cuota_mensual,
    rechazar_pago,
    registrar_pago,
    renovar_contrato,
    rescindir_contrato,
)

from xhtml2pdf import pisa

from .forms import (
    AprobarPagoForm,
    ContratoForm,
    CuotaEditForm,
    CuotaPersonalizadaForm,
    FotoInmuebleFormSet,
    InmuebleForm,
    InquilinoForm,
    MultaEditForm,
    MultaForm,
    PagoForm,
    PropietarioForm,
    RenovarContratoForm,
)
from .models import Contrato, Cuota, DocumentoContrato, Inmueble, Inquilino, Pago, Propietario, Recibo

User = get_user_model()


# --- Inquilinos ---

def _render_contact_form(request, form, contact_type, *, editando=False):
    return render(
        request,
        "inmuebles/contact_form.html",
        {"form": form, "contact_type": contact_type, "editando": editando},
    )

@login_required
def inquilino_list(request):
    inquilinos = Inquilino.objects.filter(cuenta=request.cuenta)
    return render(
        request,
        "inmuebles/inquilino_list.html",
        {"inquilinos": inquilinos, "account": request.cuenta},
    )


@login_required
def inquilino_detail(request, pk):
    inquilino = get_object_or_404(Inquilino, pk=pk, cuenta=request.cuenta)
    activos = contratos_activos_inquilino(inquilino)
    vencidos = contratos_vencidos_inquilino(inquilino)
    return render(request, "inmuebles/inquilino_detail.html", {
        "inquilino": inquilino,
        "contratos_activos": activos,
        "contratos_vencidos": vencidos,
    })


@login_required
def inquilino_create(request):
    if request.method == "POST":
        form = InquilinoForm(request.POST)
        if form.is_valid():
            try:
                inquilino = crear_inquilino(
                    nombre=form.cleaned_data["nombre"],
                    creado_por=request.user,
                    cuenta=request.cuenta,
                    email=form.cleaned_data.get("email", ""),
                    telefono=form.cleaned_data.get("telefono", ""),
                    documento=form.cleaned_data.get("documento", ""),
                    direccion=form.cleaned_data.get("direccion", ""),
                    notas=form.cleaned_data.get("notas", ""),
                )
            except InquilinoError as e:
                form.add_error(e.field, e.message)
                return _render_contact_form(request, form, "tenant")
            return redirect("inmuebles:inquilino_detail", pk=inquilino.pk)
    else:
        form = InquilinoForm()
    return _render_contact_form(request, form, "tenant")


@login_required
def inquilino_update(request, pk):
    inquilino = get_object_or_404(Inquilino, pk=pk, cuenta=request.cuenta)
    if request.method == "POST":
        form = InquilinoForm(request.POST, instance=inquilino)
        if form.is_valid():
            try:
                actualizar_inquilino(
                    inquilino,
                    nombre=form.cleaned_data.get("nombre"),
                    email=form.cleaned_data.get("email", ""),
                    telefono=form.cleaned_data.get("telefono", ""),
                    documento=form.cleaned_data.get("documento", ""),
                    direccion=form.cleaned_data.get("direccion", ""),
                    notas=form.cleaned_data.get("notas", ""),
                )
            except InquilinoError as e:
                form.add_error(e.field, e.message)
                return _render_contact_form(request, form, "tenant", editando=True)
            return redirect("inmuebles:inquilino_detail", pk=inquilino.pk)
    else:
        form = InquilinoForm(instance=inquilino)
    return _render_contact_form(request, form, "tenant", editando=True)


@login_required
def inquilino_delete(request, pk):
    inquilino = get_object_or_404(Inquilino, pk=pk, cuenta=request.cuenta)
    if request.method == "POST":
        inquilino.delete()
        return redirect("inmuebles:inquilino_list")
    return render(request, "inmuebles/inquilino_confirm_delete.html", {"inquilino": inquilino})


# --- Propietarios ---

@login_required
def propietario_list(request):
    propietarios = Propietario.objects.filter(cuenta=request.cuenta)
    return render(request, "inmuebles/propietario_list.html", {"propietarios": propietarios})


@login_required
def propietario_detail(request, pk):
    propietario = get_object_or_404(Propietario, pk=pk, cuenta=request.cuenta)
    inmuebles = propietario.inmuebles.all()
    return render(request, "inmuebles/propietario_detail.html", {"propietario": propietario, "inmuebles": inmuebles})


@login_required
def propietario_create(request):
    if request.method == "POST":
        form = PropietarioForm(request.POST)
        if form.is_valid():
            try:
                propietario = crear_propietario(
                    nombre=form.cleaned_data["nombre"],
                    creado_por=request.user,
                    cuenta=request.cuenta,
                    email=form.cleaned_data.get("email", ""),
                    telefono=form.cleaned_data.get("telefono", ""),
                    documento=form.cleaned_data.get("documento", ""),
                    direccion=form.cleaned_data.get("direccion", ""),
                    notas=form.cleaned_data.get("notas", ""),
                )
            except PropietarioError as e:
                form.add_error(e.field, e.message)
                return _render_contact_form(request, form, "owner")
            return redirect("inmuebles:propietario_detail", pk=propietario.pk)
    else:
        form = PropietarioForm()
    return _render_contact_form(request, form, "owner")


@login_required
def propietario_update(request, pk):
    propietario = get_object_or_404(Propietario, pk=pk, cuenta=request.cuenta)
    if request.method == "POST":
        form = PropietarioForm(request.POST, instance=propietario)
        if form.is_valid():
            try:
                actualizar_propietario(
                    propietario,
                    nombre=form.cleaned_data.get("nombre"),
                    email=form.cleaned_data.get("email", ""),
                    telefono=form.cleaned_data.get("telefono", ""),
                    documento=form.cleaned_data.get("documento", ""),
                    direccion=form.cleaned_data.get("direccion", ""),
                    notas=form.cleaned_data.get("notas", ""),
                )
            except PropietarioError as e:
                form.add_error(e.field, e.message)
                return _render_contact_form(request, form, "owner", editando=True)
            return redirect("inmuebles:propietario_detail", pk=propietario.pk)
    else:
        form = PropietarioForm(instance=propietario)
    return _render_contact_form(request, form, "owner", editando=True)


@login_required
def propietario_delete(request, pk):
    propietario = get_object_or_404(Propietario, pk=pk, cuenta=request.cuenta)
    if request.method == "POST":
        propietario.delete()
        return redirect("inmuebles:propietario_list")
    return render(request, "inmuebles/propietario_confirm_delete.html", {"propietario": propietario})


# --- Inmuebles ---

@login_required
def inmueble_list(request):
    inmuebles = Inmueble.objects.filter(cuenta=request.cuenta).annotate(
        contratos_alquiler_activos=Count("contratos", filter=Q(contratos__tipo=Contrato.Tipo.ALQUILER, contratos__estado=Contrato.Estado.ACTIVO)),
    )
    return render(request, "inmuebles/inmueble_list.html", {"inmuebles": inmuebles})


@login_required
def inmuebles_disponibles(request):
    inmuebles = Inmueble.objects.filter(estado=Inmueble.Estado.DISPONIBLE, cuenta=request.cuenta).annotate(
        contratos_alquiler_activos=Count("contratos", filter=Q(contratos__tipo=Contrato.Tipo.ALQUILER, contratos__estado=Contrato.Estado.ACTIVO)),
    )
    return render(request, "inmuebles/inmuebles_disponibles.html", {"inmuebles": inmuebles})


@login_required
def inmueble_detail(request, pk):
    inmueble = get_object_or_404(Inmueble, pk=pk, cuenta=request.cuenta)
    contratos_alquiler_activos = inmueble.contratos.filter(
        tipo=Contrato.Tipo.ALQUILER, estado=Contrato.Estado.ACTIVO
    ).count()
    return render(request, "inmuebles/inmueble_detail.html", {
        "inmueble": inmueble,
        "contratos_alquiler_activos": contratos_alquiler_activos,
    })


@login_required
def inmueble_create(request):
    if request.method == "POST":
        form = InmuebleForm(request.POST, cuenta=request.cuenta)
        fotos_formset = FotoInmuebleFormSet(request.POST, request.FILES)
        if form.is_valid():
            try:
                inmueble = crear_inmueble(
                    titulo=form.cleaned_data["titulo"],
                    direccion=form.cleaned_data["direccion"],
                    creado_por=request.user,
                    cuenta=request.cuenta,
                    descripcion=form.cleaned_data.get("descripcion", ""),
                    precio=form.cleaned_data.get("precio"),
                    moneda=form.cleaned_data.get("moneda"),
                    tipo=form.cleaned_data.get("tipo", Inmueble.Tipo.OTRO),
                    estado=form.cleaned_data.get("estado", Inmueble.Estado.DISPONIBLE),
                    propietario=form.cleaned_data.get("propietario"),
                    superficie=form.cleaned_data.get("superficie"),
                    habitaciones=form.cleaned_data.get("habitaciones"),
                    banos=form.cleaned_data.get("banos"),
                    latitud=form.cleaned_data.get("latitud"),
                    longitud=form.cleaned_data.get("longitud"),
                )
            except InmuebleError as e:
                form.add_error(e.field, e.message)
                return render(request, "inmuebles/inmueble_form.html", {"form": form, "fotos_formset": fotos_formset})
            fotos_formset = FotoInmuebleFormSet(request.POST, request.FILES, instance=inmueble)
            if fotos_formset.is_valid():
                fotos_formset.save()
            return redirect("inmuebles:detail", pk=inmueble.pk)
    else:
        form = InmuebleForm(cuenta=request.cuenta)
        fotos_formset = FotoInmuebleFormSet()
    return render(request, "inmuebles/inmueble_form.html", {"form": form, "fotos_formset": fotos_formset})


@login_required
def inmueble_update(request, pk):
    inmueble = get_object_or_404(Inmueble, pk=pk, cuenta=request.cuenta)
    if request.method == "POST":
        form = InmuebleForm(request.POST, instance=inmueble, cuenta=request.cuenta)
        fotos_formset = FotoInmuebleFormSet(request.POST, request.FILES, instance=inmueble)
        if form.is_valid():
            try:
                actualizar_inmueble(
                    inmueble,
                    titulo=form.cleaned_data.get("titulo"),
                    direccion=form.cleaned_data.get("direccion"),
                    descripcion=form.cleaned_data.get("descripcion"),
                    precio=form.cleaned_data.get("precio"),
                    moneda=form.cleaned_data.get("moneda"),
                    tipo=form.cleaned_data.get("tipo"),
                    estado=form.cleaned_data.get("estado"),
                    propietario=form.cleaned_data.get("propietario"),
                    superficie=form.cleaned_data.get("superficie"),
                    habitaciones=form.cleaned_data.get("habitaciones"),
                    banos=form.cleaned_data.get("banos"),
                    tipo_alquiler=form.cleaned_data.get("tipo_alquiler"),
                    latitud=form.cleaned_data.get("latitud"),
                    longitud=form.cleaned_data.get("longitud"),
                )
            except InmuebleError as e:
                form.add_error(e.field, e.message)
                return render(request, "inmuebles/inmueble_form.html", {"form": form, "fotos_formset": fotos_formset, "editando": True})
            if fotos_formset.is_valid():
                fotos_formset.save()
            return redirect("inmuebles:list")
    else:
        form = InmuebleForm(instance=inmueble, cuenta=request.cuenta)
        fotos_formset = FotoInmuebleFormSet(instance=inmueble)
    return render(request, "inmuebles/inmueble_form.html", {"form": form, "fotos_formset": fotos_formset, "editando": True})


@login_required
def inmueble_delete(request, pk):
    inmueble = get_object_or_404(Inmueble, pk=pk, cuenta=request.cuenta)
    if request.method == "POST":
        inmueble.delete()
        return redirect("inmuebles:list")
    return render(request, "inmuebles/inmueble_confirm_delete.html", {"inmueble": inmueble})


# --- Contratos ---

@login_required
def contrato_list(request, inmueble_pk):
    inmueble = get_object_or_404(Inmueble, pk=inmueble_pk, cuenta=request.cuenta)
    contratos = inmueble.contratos.all()
    return render(request, "inmuebles/contrato_list.html", {"inmueble": inmueble, "contratos": contratos})


@login_required
def contrato_create(request, inmueble_pk):
    inmueble = get_object_or_404(Inmueble, pk=inmueble_pk, cuenta=request.cuenta)
    if request.method == "POST":
        form = ContratoForm(request.POST, cuenta=request.cuenta)
        if form.is_valid():
            try:
                contrato = crear_contrato(
                    inmueble=inmueble,
                    tipo=form.cleaned_data["tipo"],
                    creado_por=request.user,
                    inquilino=form.cleaned_data.get("inquilino"),
                    inquilino_registrado=form.cleaned_data.get("inquilino_registrado"),
                    inquilino_nombre=form.cleaned_data.get("inquilino_nombre", ""),
                    inquilino_email=form.cleaned_data.get("inquilino_email", ""),
                    inquilino_telefono=form.cleaned_data.get("inquilino_telefono", ""),
                    frecuencia_pago=form.cleaned_data["frecuencia_pago"],
                    duracion_anos=form.cleaned_data.get("duracion_anos"),
                    fecha_inicio=form.cleaned_data["fecha_inicio"],
                    fecha_fin=form.cleaned_data.get("fecha_fin"),
                    monto=form.cleaned_data["monto"],
                    moneda=form.cleaned_data["moneda"],
                    comision=form.cleaned_data.get("comision"),
                    garantia=form.cleaned_data.get("garantia"),
                )
            except ContratoError as e:
                if e.field in form.fields:
                    form.add_error(e.field, e.message)
                else:
                    form.add_error(None, e.message)
                return render(request, "inmuebles/contrato_form.html", {"form": form, "inmueble": inmueble})
            return redirect("inmuebles:contrato_detail", pk=contrato.pk)
    else:
        initial = {}
        tipo = request.GET.get("tipo")
        if tipo in dict(Contrato.Tipo.choices):
            initial["tipo"] = tipo
        initial["moneda"] = inmueble.moneda
        form = ContratoForm(initial=initial, cuenta=request.cuenta)
    tipo_fijo = request.GET.get("tipo") if request.GET.get("tipo") in dict(Contrato.Tipo.choices) else None
    tipo_display = dict(Contrato.Tipo.choices).get(tipo_fijo) if tipo_fijo else None
    return render(request, "inmuebles/contrato_form.html", {"form": form, "inmueble": inmueble, "tipo_fijo": tipo_fijo, "tipo_display": tipo_display})


@login_required
def contrato_detail(request, pk):
    contrato = get_object_or_404(Contrato, pk=pk, inmueble__cuenta=request.cuenta)
    return render(request, "inmuebles/contrato_detail.html", {"contrato": contrato})


@login_required
def contrato_global_list(request):
    base_qs = Contrato.objects.filter(inmueble__cuenta=request.cuenta)
    tipo = request.GET.get("tipo")
    if tipo:
        contratos = base_qs.filter(tipo=tipo)
    else:
        contratos = base_qs
    total = base_qs.count()
    alq_count = base_qs.filter(tipo=Contrato.Tipo.ALQUILER).count()
    aut_count = base_qs.filter(tipo=Contrato.Tipo.AUTORIZACION_VENTA).count()

    contratos_agrupados = {}
    for c in base_qs:
        tipo_display = c.get_tipo_display()
        contratos_agrupados.setdefault(tipo_display, []).append(c)

    return render(request, "inmuebles/contrato_list.html", {
        "contratos": contratos, "global": True, "tipo_actual": tipo,
        "total_count": total, "alquiler_count": alq_count, "autorizacion_count": aut_count,
        "todos_contratos": base_qs, "contratos_agrupados": contratos_agrupados,
        "inmuebles": Inmueble.objects.filter(cuenta=request.cuenta),
    })


@login_required
def contrato_update(request, pk):
    contrato = get_object_or_404(Contrato, pk=pk, inmueble__cuenta=request.cuenta)
    if request.method == "POST":
        form = ContratoForm(request.POST, instance=contrato, cuenta=request.cuenta)
        if form.is_valid():
            try:
                actualizar_contrato(
                    contrato,
                    tipo=form.cleaned_data.get("tipo"),
                    inquilino=form.cleaned_data.get("inquilino"),
                    inquilino_registrado=form.cleaned_data.get("inquilino_registrado"),
                    inquilino_nombre=form.cleaned_data.get("inquilino_nombre"),
                    inquilino_email=form.cleaned_data.get("inquilino_email"),
                    inquilino_telefono=form.cleaned_data.get("inquilino_telefono"),
                    frecuencia_pago=form.cleaned_data.get("frecuencia_pago"),
                    duracion_anos=form.cleaned_data.get("duracion_anos"),
                    fecha_inicio=form.cleaned_data.get("fecha_inicio"),
                    fecha_fin=form.cleaned_data.get("fecha_fin"),
                    monto=form.cleaned_data.get("monto"),
                    moneda=form.cleaned_data.get("moneda"),
                    comision=form.cleaned_data.get("comision"),
                    garantia=form.cleaned_data.get("garantia"),
                )
            except ContratoError as e:
                form.add_error(e.field, e.message)
                return render(request, "inmuebles/contrato_form.html", {"form": form, "inmueble": contrato.inmueble, "editando": True})
            return redirect("inmuebles:contrato_detail", pk=contrato.pk)
    else:
        form = ContratoForm(instance=contrato, cuenta=request.cuenta)
    return render(request, "inmuebles/contrato_form.html", {"form": form, "inmueble": contrato.inmueble, "editando": True})


@login_required
def contrato_renovar(request, pk):
    contrato = get_object_or_404(Contrato, pk=pk, inmueble__cuenta=request.cuenta)
    if contrato.estado != Contrato.Estado.ACTIVO:
        return redirect("inmuebles:contrato_detail", pk=contrato.pk)
    default_fecha_inicio = (contrato.fecha_fin or (contrato.fecha_inicio + timedelta(days=365))) + timedelta(days=1)
    if request.method == "POST":
        form = RenovarContratoForm(request.POST)
        if form.is_valid():
            try:
                nuevo = renovar_contrato(
                    contrato_actual=contrato,
                    fecha_inicio=form.cleaned_data["fecha_inicio"],
                    fecha_fin=form.cleaned_data.get("fecha_fin"),
                    monto=form.cleaned_data["monto"],
                    moneda=form.cleaned_data["moneda"],
                    comision=form.cleaned_data.get("comision"),
                )
            except ContratoError as e:
                form.add_error(e.field, e.message)
                return render(request, "inmuebles/contrato_renovar.html", {"form": form, "contrato": contrato})
            return redirect("inmuebles:contrato_detail", pk=nuevo.pk)
    else:
        initial = {
            "fecha_inicio": default_fecha_inicio,
            "monto": contrato.monto,
            "moneda": contrato.moneda,
            "comision": contrato.comision,
        }
        form = RenovarContratoForm(initial=initial)
    return render(request, "inmuebles/contrato_renovar.html", {"form": form, "contrato": contrato})


@login_required
def contrato_finalizar(request, pk):
    contrato = get_object_or_404(Contrato, pk=pk, inmueble__cuenta=request.cuenta)
    if contrato.estado != Contrato.Estado.ACTIVO:
        return redirect("inmuebles:contrato_detail", pk=contrato.pk)
    if request.method == "POST":
        finalizar_contrato(contrato)
        return redirect("inmuebles:contrato_detail", pk=contrato.pk)
    return render(request, "inmuebles/contrato_confirm_finalizar.html", {"contrato": contrato, "accion": "finalizar"})


@login_required
def contrato_rescindir(request, pk):
    contrato = get_object_or_404(Contrato, pk=pk, inmueble__cuenta=request.cuenta)
    if contrato.estado != Contrato.Estado.ACTIVO:
        return redirect("inmuebles:contrato_detail", pk=contrato.pk)
    if request.method == "POST":
        rescindir_contrato(contrato)
        return redirect("inmuebles:contrato_detail", pk=contrato.pk)
    return render(request, "inmuebles/contrato_confirm_finalizar.html", {"contrato": contrato, "accion": "rescindir"})


@login_required
def descargar_documento(request, pk):
    doc = get_object_or_404(DocumentoContrato, pk=pk, contrato__inmueble__cuenta=request.cuenta)
    response = HttpResponse(doc.archivo, content_type=doc.content_type)
    response["Content-Disposition"] = f'attachment; filename="{doc.nombre}"'
    return response


@login_required
def descargar_comprobante(request, pk):
    pago = get_object_or_404(
        Pago.objects.select_related(
            "cuota__contrato__inmueble", "cuota__contrato__inquilino_registrado"
        ),
        pk=pk,
        cuota__contrato__inmueble__cuenta=request.cuenta,
    )
    contrato = pago.cuota.contrato
    membership = getattr(request, "membership", None)
    is_admin = request.user.is_superuser or (membership and membership.is_admin)
    is_tenant = contrato.inquilino_id == request.user.id or (
        contrato.inquilino_registrado
        and contrato.inquilino_registrado.user_id == request.user.id
    )
    if not is_admin and not is_tenant:
        raise PermissionDenied
    if not pago.archivo_comprobante:
        raise Http404
    return FileResponse(
        pago.archivo_comprobante.open("rb"),
        as_attachment=True,
        filename=Path(pago.archivo_comprobante.name).name,
    )


# ---------------------------------------------------------------------------
# Cobros - Cuotas
# ---------------------------------------------------------------------------

@login_required
def cuota_list(request, contrato_pk):
    contrato = get_object_or_404(Contrato, pk=contrato_pk, inmueble__cuenta=request.cuenta)
    cuotas = contrato.cuotas.all()
    for c in cuotas:
        if c.estado in (Cuota.Estado.PENDIENTE, Cuota.Estado.PARCIAL):
            actualizar_estado_cuota(c)
    cuotas = contrato.cuotas.all()
    saldo = sum(c.total for c in cuotas if c.estado not in (Cuota.Estado.PAGADO,))
    return render(request, "inmuebles/cuota_list.html", {
        "contrato": contrato, "cuotas": cuotas, "saldo": saldo,
    })


@login_required
def cuota_create_mensual(request, contrato_pk):
    contrato = get_object_or_404(Contrato, pk=contrato_pk, inmueble__cuenta=request.cuenta)
    if request.method == "POST":
        try:
            generar_cuota_mensual(contrato=contrato, creado_por=request.user)
        except CuotaError as e:
            messages.error(request, e.message)
        return redirect("inmuebles:cuota_list", contrato_pk=contrato.pk)
    return redirect("inmuebles:cuota_list", contrato_pk=contrato.pk)


@login_required
def cuota_create_personalizada(request, contrato_pk):
    contrato = get_object_or_404(Contrato, pk=contrato_pk, inmueble__cuenta=request.cuenta)
    if request.method == "POST":
        form = CuotaPersonalizadaForm(request.POST)
        if form.is_valid():
            try:
                crear_cuota_personalizada(
                    contrato=contrato,
                    monto=form.cleaned_data["monto"],
                    descripcion=form.cleaned_data["descripcion"],
                    fecha_vencimiento=form.cleaned_data["fecha_vencimiento"],
                    creado_por=request.user,
                )
            except CuotaError as e:
                form.add_error(e.field, e.message)
                return render(request, "inmuebles/cuota_form.html", {"form": form, "contrato": contrato})
            return redirect("inmuebles:cuota_list", contrato_pk=contrato.pk)
    else:
        form = CuotaPersonalizadaForm()
    return render(request, "inmuebles/cuota_form.html", {"form": form, "contrato": contrato})


@login_required
def cuota_update(request, pk):
    cuota = get_object_or_404(Cuota, pk=pk, contrato__inmueble__cuenta=request.cuenta)
    if request.method == "POST":
        form = CuotaEditForm(request.POST, instance=cuota)
        if form.is_valid():
            try:
                actualizar_cuota(
                    cuota,
                    descripcion=form.cleaned_data.get("descripcion"),
                    monto=form.cleaned_data.get("monto"),
                    fecha_vencimiento=form.cleaned_data.get("fecha_vencimiento"),
                )
            except CuotaError as e:
                form.add_error(e.field, e.message)
                return render(request, "inmuebles/cuota_edit.html", {"form": form, "cuota": cuota})
            return redirect("inmuebles:cuota_list", contrato_pk=cuota.contrato.pk)
    else:
        form = CuotaEditForm(instance=cuota)
    return render(request, "inmuebles/cuota_edit.html", {"form": form, "cuota": cuota})


# ---------------------------------------------------------------------------
# Cobros - Pagos
# ---------------------------------------------------------------------------

@login_required
def pago_list(request, cuota_pk):
    cuota = get_object_or_404(Cuota, pk=cuota_pk, contrato__inmueble__cuenta=request.cuenta)
    pagos = cuota.pagos.all()
    return render(request, "inmuebles/pago_list.html", {"cuota": cuota, "pagos": pagos})


@login_required
def pago_create(request, cuota_pk):
    cuota = get_object_or_404(Cuota, pk=cuota_pk, contrato__inmueble__cuenta=request.cuenta)
    if request.method == "POST":
        form = PagoForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                registrar_pago(
                    cuota=cuota,
                    monto=form.cleaned_data["monto"],
                    fecha_pago=form.cleaned_data["fecha_pago"],
                    metodo_pago=form.cleaned_data["metodo_pago"],
                    creado_por=request.user,
                    archivo_comprobante=form.cleaned_data.get("archivo_comprobante"),
                    comprobante=form.cleaned_data.get("comprobante", ""),
                    observaciones=form.cleaned_data.get("observaciones", ""),
                )
            except PagoError as e:
                form.add_error(e.field, e.message)
                return render(request, "inmuebles/pago_form.html", {"form": form, "cuota": cuota})
            return redirect("inmuebles:cuota_list", contrato_pk=cuota.contrato.pk)
    else:
        form = PagoForm(initial={"monto": cuota.total, "fecha_pago": date.today()})
    return render(request, "inmuebles/pago_form.html", {"form": form, "cuota": cuota})


@login_required
def pago_pendientes(request):
    pagos = Pago.objects.filter(estado=Pago.Estado.PENDIENTE, cuota__contrato__inmueble__cuenta=request.cuenta)
    return render(request, "inmuebles/pago_pendientes.html", {"pagos": pagos})


@login_required
def pago_registro(request):
    pagos = Pago.objects.filter(cuota__contrato__inmueble__cuenta=request.cuenta).select_related(
        "cuota__contrato__inmueble"
    )
    return render(request, "inmuebles/pago_registro.html", {"pagos": pagos})


@login_required
def pago_aprobar_rechazar(request, pk):
    pago = get_object_or_404(Pago, pk=pk, estado=Pago.Estado.PENDIENTE, cuota__contrato__inmueble__cuenta=request.cuenta)
    if request.method == "POST":
        form = AprobarPagoForm(request.POST)
        if form.is_valid():
            try:
                if form.cleaned_data["accion"] == "aprobar":
                    aprobar_pago(pago)
                    _notificar_aprobacion(pago)
                    messages.success(request, "Pago aprobado correctamente.")
                else:
                    motivo = form.cleaned_data.get("motivo_rechazo", "")
                    rechazar_pago(pago, motivo=motivo)
                    _notificar_rechazo(pago, motivo)
                    messages.warning(request, "Pago rechazado.")
            except PagoError as e:
                form.add_error("accion", e.message)
                return render(request, "inmuebles/pago_aprobar_rechazar.html", {"form": form, "pago": pago})
            return redirect("inmuebles:pago_pendientes")
    else:
        form = AprobarPagoForm()
    return render(request, "inmuebles/pago_aprobar_rechazar.html", {"form": form, "pago": pago})


def _notificar_aprobacion(pago):
    _enviar_email_pago(pago, "aprobado", f"Tu pago de {pago.moneda} {pago.monto} fue aprobado. Podés descargar tu recibo.")


def _notificar_rechazo(pago, motivo):
    _enviar_email_pago(pago, "rechazado", f"Tu pago de {pago.moneda} {pago.monto} fue rechazado. Motivo: {motivo}")


def _enviar_email_pago(pago, asunto, mensaje):
    from django.core.mail import send_mail
    contrato = pago.cuota.contrato
    email = contrato.inquilino_email or (
        contrato.inquilino_registrado.email if contrato.inquilino_registrado else ""
    )
    if email:
        send_mail(
            f"Pago {asunto} - {contrato.inmueble.titulo}",
            mensaje,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=True,
        )


@login_required
def recibo_descargar(request, pk):
    recibo = get_object_or_404(Recibo, pk=pk, pago__cuota__contrato__inmueble__cuenta=request.cuenta)
    pago = recibo.pago
    ctx = {
        "recibo": recibo,
        "pago": pago,
        "cuota": pago.cuota,
        "contrato": pago.cuota.contrato,
        "inmueble": pago.cuota.contrato.inmueble,
    }
    html = render_to_string("inmuebles/recibo_pdf.html", ctx)
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="recibo_{recibo.codigo}.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse("Error al generar PDF", status=500)
    return response


# ---------------------------------------------------------------------------
# Cobros - Multas
# ---------------------------------------------------------------------------

@login_required
def cuota_aplicar_multa(request, cuota_pk):
    cuota = get_object_or_404(Cuota, pk=cuota_pk, contrato__inmueble__cuenta=request.cuenta)
    if request.method == "POST":
        form = MultaForm(request.POST)
        if form.is_valid():
            try:
                aplicar_multa(
                    cuota=cuota,
                    monto_fijo=form.cleaned_data.get("monto_fijo"),
                    porcentaje=form.cleaned_data.get("porcentaje"),
                    motivo=form.cleaned_data.get("motivo", ""),
                )
            except CuotaError as e:
                form.add_error("monto_fijo", e.message)
                return render(request, "inmuebles/multa_form.html", {"form": form, "cuota": cuota})
            return redirect("inmuebles:cuota_list", contrato_pk=cuota.contrato.pk)
    else:
        form = MultaForm()
    return render(request, "inmuebles/multa_form.html", {"form": form, "cuota": cuota})


@login_required
def cuota_editar_multa(request, cuota_pk):
    cuota = get_object_or_404(Cuota, pk=cuota_pk, contrato__inmueble__cuenta=request.cuenta)
    if request.method == "POST":
        form = MultaEditForm(request.POST, instance=cuota)
        if form.is_valid():
            form.save()
            return redirect("inmuebles:cuota_list", contrato_pk=cuota.contrato.pk)
    else:
        form = MultaEditForm(instance=cuota)
    return render(request, "inmuebles/multa_edit.html", {"form": form, "cuota": cuota})


@login_required
def cuota_eliminar_multa(request, cuota_pk):
    cuota = get_object_or_404(Cuota, pk=cuota_pk, contrato__inmueble__cuenta=request.cuenta)
    if request.method == "POST":
        Cuota.objects.filter(pk=cuota.pk).update(monto_multa=0)
    return redirect("inmuebles:cuota_list", contrato_pk=cuota.contrato.pk)


# ---------------------------------------------------------------------------
# Portal del inquilino
# ---------------------------------------------------------------------------

def _get_inquilino_for_user(user, cuenta=None):
    return Inquilino.objects.filter(user=user, cuenta=cuenta).first()


@login_required
def portal(request):
    inquilino = _get_inquilino_for_user(request.user, request.cuenta)
    if not inquilino:
        return redirect("core:home")
    contratos = Contrato.objects.filter(
        Q(inquilino_registrado=inquilino) | Q(inquilino=request.user)
    )
    activos = contratos.filter(estado=Contrato.Estado.ACTIVO)
    cuotas_pendientes = Cuota.objects.filter(
        contrato__in=activos,
        estado__in=(Cuota.Estado.PENDIENTE, Cuota.Estado.VENCIDO, Cuota.Estado.PARCIAL),
    )
    totals = {}
    for cuota in cuotas_pendientes.select_related("contrato"):
        totals[cuota.moneda] = totals.get(cuota.moneda, 0) + cuota.total
    return render(request, "inmuebles/portal_dashboard.html", {
        "inquilino": inquilino,
        "contratos_activos_count": activos.count(),
        "cuotas_pendientes_count": cuotas_pendientes.count(),
        "totales_adeudados": sorted(totals.items()),
        "contratos_recientes": activos[:5],
    })


@login_required
def portal_contratos(request):
    inquilino = _get_inquilino_for_user(request.user, request.cuenta)
    if not inquilino:
        return redirect("core:home")
    contratos = Contrato.objects.filter(
        Q(inquilino_registrado=inquilino) | Q(inquilino=request.user)
    ).select_related("inmueble")
    for c in contratos:
        c.es_inquilino_registrado = c.inquilino_registrado is not None
    return render(request, "inmuebles/portal_contratos.html", {
        "inquilino": inquilino,
        "contratos": contratos,
    })


@login_required
def portal_cuotas(request, contrato_pk):
    inquilino = _get_inquilino_for_user(request.user, request.cuenta)
    if not inquilino:
        return redirect("core:home")
    contrato = get_object_or_404(
        Contrato, pk=contrato_pk,
        inquilino_registrado=inquilino,
    )
    cuotas = contrato.cuotas.all()
    for c in cuotas:
        if c.estado in (Cuota.Estado.PENDIENTE, Cuota.Estado.PARCIAL):
            actualizar_estado_cuota(c)
    cuotas = contrato.cuotas.all()
    saldo = sum(c.total for c in cuotas if c.estado != Cuota.Estado.PAGADO)
    return render(request, "inmuebles/portal_cuotas.html", {
        "inquilino": inquilino,
        "contrato": contrato,
        "cuotas": cuotas,
        "saldo": saldo,
    })


@login_required
def portal_pago_detalle(request, pk):
    inquilino = _get_inquilino_for_user(request.user, request.cuenta)
    if not inquilino:
        return redirect("core:home")
    pago = get_object_or_404(
        Pago, pk=pk,
        cuota__contrato__inquilino_registrado=inquilino,
    )
    return render(request, "inmuebles/portal_pago_detalle.html", {
        "inquilino": inquilino,
        "pago": pago,
    })


@login_required
def portal_pago_subir(request, cuota_pk):
    inquilino = _get_inquilino_for_user(request.user, request.cuenta)
    if not inquilino:
        return redirect("core:home")
    cuota = get_object_or_404(
        Cuota, pk=cuota_pk,
        contrato__inquilino_registrado=inquilino,
    )
    if request.method == "POST":
        form = PagoForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                registrar_pago(
                    cuota=cuota,
                    monto=form.cleaned_data["monto"],
                    fecha_pago=form.cleaned_data["fecha_pago"],
                    metodo_pago=form.cleaned_data["metodo_pago"],
                    creado_por=request.user,
                    archivo_comprobante=form.cleaned_data.get("archivo_comprobante"),
                    comprobante=form.cleaned_data.get("comprobante", ""),
                    observaciones=form.cleaned_data.get("observaciones", ""),
                )
            except PagoError as e:
                form.add_error(e.field, e.message)
                return render(request, "inmuebles/portal_pago_form.html", {"form": form, "cuota": cuota, "inquilino": inquilino})
            messages.success(request, "Pago registrado. Pendiente de aprobación.")
            return redirect("inmuebles:portal_cuotas", contrato_pk=cuota.contrato.pk)
    else:
        form = PagoForm(initial={"monto": cuota.total, "fecha_pago": date.today()})
    return render(request, "inmuebles/portal_pago_form.html", {"form": form, "cuota": cuota, "inquilino": inquilino})


@login_required
def portal_proximos_pagos(request):
    """Mostrar cuotas pendientes y pagos recientes del inquilino."""
    inquilino = _get_inquilino_for_user(request.user, request.cuenta)
    if not inquilino:
        return redirect("core:home")

    contratos = Contrato.objects.filter(
        Q(inquilino_registrado=inquilino) | Q(inquilino=request.user)
    )

    # Cuotas pendientes (no pagadas)
    cuotas_pendientes = Cuota.objects.filter(
        contrato__in=contratos,
        estado__in=(Cuota.Estado.PENDIENTE, Cuota.Estado.VENCIDO, Cuota.Estado.PARCIAL),
    ).select_related("contrato", "contrato__inmueble").order_by("fecha_vencimiento")

    # Pagos recientes (aprobados)
    pagos_recientes = Pago.objects.filter(
        cuota__contrato__in=contratos,
        estado__in=(Pago.Estado.APROBADO, Pago.Estado.PENDIENTE),
    ).select_related("cuota", "cuota__contrato", "cuota__contrato__inmueble").order_by("-fecha_pago")[:10]

    return render(request, "inmuebles/portal_proximos_pagos.html", {
        "inquilino": inquilino,
        "cuotas_pendientes": cuotas_pendientes,
        "pagos_recientes": pagos_recientes,
    })


# ---------------------------------------------------------------------------
# Admin inquilino: crear usuario y desvincular
# ---------------------------------------------------------------------------

@login_required
def inquilino_create_user(request, pk):
    inquilino = get_object_or_404(Inquilino, pk=pk, cuenta=request.cuenta)
    if request.method == "POST":
        from apps.users.services import crear_usuario_inquilino
        try:
            user, temp_password, security_code = crear_usuario_inquilino(inquilino, request)
            messages.success(
                request,
                f"Usuario '{user.username}' creado y vinculado a {inquilino.nombre}. "
                f"Se envió un email con las credenciales de acceso.",
            )
        except ValueError as e:
            messages.error(request, str(e))
        return redirect("inmuebles:inquilino_detail", pk=pk)
    return redirect("inmuebles:inquilino_detail", pk=pk)


@login_required
def inquilino_unlink_user(request, pk):
    inquilino = get_object_or_404(Inquilino, pk=pk, cuenta=request.cuenta)
    if request.method == "POST":
        linked_user = inquilino.user
        inquilino.user = None
        inquilino.save()
        if linked_user:
            from apps.users.models import MembresiaCuenta
            MembresiaCuenta.objects.filter(
                cuenta=request.cuenta,
                user=linked_user,
                rol=MembresiaCuenta.Roles.INQUILINO,
            ).update(activa=False)
        messages.success(request, "Usuario desvinculado.")
    return redirect("inmuebles:inquilino_detail", pk=pk)


# ---------------------------------------------------------------------------
# Carga masiva desde Excel
# ---------------------------------------------------------------------------

@login_required
def descargar_plantilla_excel(request):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.comments import Comment
    from django.http import HttpResponse

    wb = Workbook()
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    required_header_fill = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
    section_font = Font(bold=True, size=11, color="1F4E79")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    def _col_letter(idx):
        result = ""
        while idx > 0:
            idx, rem = divmod(idx - 1, 26)
            result = chr(65 + rem) + result
        return result

    def _setup_sheet(ws, headers, required_cols, example_row, comments=None):
        for col_idx, (header, is_required) in enumerate(zip(headers, required_cols), start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = required_header_fill if is_required else header_fill
            cell.alignment = Alignment(horizontal="center")
            cell.border = thin_border
            if comments and col_idx in comments:
                cell.comment = Comment(comments[col_idx], "Sistema")
                cell.comment.width = 300
                cell.comment.height = 120
        for col_idx, val in enumerate(example_row, start=1):
            cell = ws.cell(row=2, column=col_idx, value=val)
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="left")
        for col_idx in range(1, len(headers) + 1):
            ws.column_dimensions[_col_letter(col_idx)].width = 22

    # --- Hoja Instrucciones ---
    ws_inst = wb.active
    ws_inst.title = "Instrucciones"
    ws_inst.column_dimensions["A"].width = 30
    ws_inst.column_dimensions["B"].width = 50
    ws_inst.column_dimensions["C"].width = 50

    instrucciones = [
        ("", "", ""),
        ("PLANTILLA DE CARGA DE DATOS", "", ""),
        ("", "", ""),
        ("HOJAS DEL ARCHIVO", "", ""),
        ("Hoja", "Descripcion", "Campos obligatorios"),
        ("Inquilinos", "Datos de inquilinos (arrendatarios)", "nombre"),
        ("Propietarios", "Datos de propietarios de inmuebles", "nombre"),
        ("Inmuebles", "Datos de inmuebles (propiedades)", "titulo, direccion, tipo, estado"),
        ("", "", ""),
        ("CAMPOS CON OPCIONES LIMITADAS", "Hoja: Inmuebles", ""),
        ("Campo", "Opciones validas", "Descripcion"),
        ("tipo", "casa, dpto, terreno, local, otro", "Tipo de inmueble"),
        ("estado", "disponible, no_disponible, alquilado, vendido, reservado", "Estado actual del inmueble"),
        ("tipo_alquiler", "completa, por_habitaciones, por_local", "Modalidad de alquiler"),
        ("", "", ""),
        ("REGLAS GENERALES", "", ""),
        ("", "1. Los campos con fondo ROJO son obligatorios.", ""),
        ("", "2. Use el menu desplegable en las columnas con opciones limitadas.", ""),
        ("", "3. El email debe tener un formato valido (ejemplo@dominio.com).", ""),
        ("", "4. El precio y superficie deben ser numeros positivos.", ""),
        ("", "5. Para inmuebles, propietario_documento debe coincidir con el", ""),
        ("", "   documento de un propietario cargado en la hoja Propietarios.", ""),
        ("", "6. Puede dejar vacios los campos no obligatorios.", ""),
        ("", "7. Elimine la fila de ejemplo (fila 2) antes de cargar sus datos.", ""),
        ("", "", ""),
        ("NOTAS", "", ""),
        ("Inquilinos", "Informacion adicional sobre el inquilino (historial, referencias, etc.)", ""),
        ("Propietarios", "Informacion adicional sobre el propietario (contacto alternativo, etc.)", ""),
        ("Inmuebles - descripcion", "Descripcion detallada del inmueble (caracteristicas, amenities, estado)", ""),
    ]

    title_font = Font(bold=True, size=14, color="1F4E79")
    subtitle_font = Font(bold=True, size=11, color="4472C4")
    for row_idx, (a, b, c) in enumerate(instrucciones, start=1):
        ws_inst.cell(row=row_idx, column=1, value=a)
        ws_inst.cell(row=row_idx, column=2, value=b)
        ws_inst.cell(row=row_idx, column=3, value=c)
        if row_idx == 2:
            ws_inst.cell(row=row_idx, column=1).font = title_font
        elif row_idx in (5, 11, 18):
            ws_inst.cell(row=row_idx, column=1).font = Font(bold=True, size=11, color="1F4E79")
            ws_inst.cell(row=row_idx, column=2).font = Font(bold=True, size=11, color="1F4E79")
            ws_inst.cell(row=row_idx, column=3).font = Font(bold=True, size=11, color="1F4E79")

    # --- Hoja Inquilinos ---
    ws_inq = wb.create_sheet("Inquilinos")
    inq_headers = ["nombre", "email", "telefono", "documento", "direccion", "notas"]
    inq_required = [True, False, False, False, False, False]
    inq_comments = {6: "NOTAS: Informacion adicional sobre el inquilino.\nPuede incluir: historial de pagos, referencias, observaciones, etc.\nEste campo es opcional."}
    _setup_sheet(ws_inq, inq_headers, inq_required, ["Juan Perez", "juan@email.com", "555-1234", "12345678", "Av. Principal 123", "Inquilino de referencia"], inq_comments)

    # --- Hoja Propietarios ---
    ws_prop = wb.create_sheet("Propietarios")
    prop_headers = ["nombre", "email", "telefono", "documento", "direccion", "notas"]
    prop_required = [True, False, False, False, False, False]
    prop_comments = {6: "NOTAS: Informacion adicional sobre el propietario.\nPuede incluir: datos bancarios, contacto alternativo, condiciones especiales, etc.\nEste campo es opcional."}
    _setup_sheet(ws_prop, prop_headers, prop_required, ["Maria Lopez", "maria@email.com", "555-5678", "87654321", "Calle Secundaria 456", "Propietaria activa"], prop_comments)

    # --- Hoja Inmuebles ---
    ws_inm = wb.create_sheet("Inmuebles")
    inm_headers = ["titulo", "direccion", "descripcion", "precio", "tipo", "estado", "propietario_documento", "superficie", "habitaciones", "banos", "tipo_alquiler"]
    inm_required = [True, True, False, False, True, True, False, False, False, False, False]
    inm_comments = {
        3: "DESCRIPCION: Detalle las caracteristicas del inmueble.\nPuede incluir: metros cuadrados, amenities, estado de conservacion, vistas, etc.",
        5: "TIPO (obligatorio): Seleccione del menu desplegable.\nOpciones: casa, dpto, terreno, local, otro",
        6: "ESTADO (obligatorio): Seleccione del menu desplegable.\nOpciones: disponible, no_disponible, alquilado, vendido, reservado",
        7: "PROPIETARIO DOCUMENTO: Numero de documento del propietario.\nDebe coincidir exactamente con un documento cargado en la hoja Propietarios.\nSi no coincide, el inmueble se cargara sin propietario.",
        11: "TIPO ALQUILER: Seleccione del menu desplegable.\nOpciones: completa (un solo inquilino), por_habitaciones (habitaciones independientes)",
    }
    _setup_sheet(ws_inm, inm_headers, inm_required, ["Casa en la playa", "Av. Costera 789", "Hermosa casa con vista al mar", "150000", "casa", "disponible", "87654321", "120.5", "3", "2", "completa"], inm_comments)

    # Data Validation: tipo (columna E)
    dv_tipo = DataValidation(
        type="list",
        formula1='"casa,dpto,terreno,local,otro"',
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="Tipo invalido",
        error="Seleccione un tipo valido: casa, dpto, terreno, local, otro",
        showInputMessage=True,
        promptTitle="Tipo de inmueble",
        prompt="Opciones: casa, dpto, terreno, local, otro",
    )
    ws_inm.add_data_validation(dv_tipo)
    dv_tipo.add(f"E3:E1000")

    # Data Validation: estado (columna F)
    dv_estado = DataValidation(
        type="list",
        formula1='"disponible,no_disponible,alquilado,vendido,reservado"',
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="Estado invalido",
        error="Seleccione un estado valido: disponible, no_disponible, alquilado, vendido, reservado",
        showInputMessage=True,
        promptTitle="Estado del inmueble",
        prompt="Opciones: disponible, no_disponible, alquilado, vendido, reservado",
    )
    ws_inm.add_data_validation(dv_estado)
    dv_estado.add(f"F3:F1000")

    # Data Validation: tipo_alquiler (columna K)
    dv_alquiler = DataValidation(
        type="list",
        formula1='"completa,por_habitaciones,por_local"',
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="Tipo de alquiler invalido",
        error="Seleccione: completa, por_habitaciones o por_local",
        showInputMessage=True,
        promptTitle="Tipo de alquiler",
        prompt="Opciones: completa, por_habitaciones, por_local",
    )
    ws_inm.add_data_validation(dv_alquiler)
    dv_alquiler.add(f"K3:K1000")

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="plantilla_carga_datos.xlsx"'
    return response


@login_required
def cargar_datos_excel(request):
    resultado = None
    if request.method == "POST" and request.FILES.get("archivo"):
        archivo = request.FILES["archivo"]
        if archivo.size > 10 * 1024 * 1024:
            resultado = {
                "valido": False,
                "mensaje": "El archivo no puede superar 10 MB.",
                "resumen": {},
                "errores": [],
                "advertencias": [],
            }
        elif not archivo.name.lower().endswith((".xlsx", ".xls")):
            resultado = {
                "valido": False,
                "mensaje": "El archivo debe ser un Excel (.xlsx o .xls).",
                "resumen": {},
                "errores": [],
                "advertencias": [],
            }
        else:
            resultado = cargar_datos_desde_excel(request.user, archivo, request.cuenta)
    return render(request, "inmuebles/carga_excel.html", {"resultado": resultado})
