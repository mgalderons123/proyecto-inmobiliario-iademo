from django.contrib import admin

from .models import Contrato, Cuota, DocumentoContrato, FotoInmueble, Inmueble, Inquilino, Pago, Propietario


class FotoInmuebleInline(admin.TabularInline):
    model = FotoInmueble
    extra = 1


@admin.register(Inquilino)
class InquilinoAdmin(admin.ModelAdmin):
    list_display = ["nombre", "documento", "email", "telefono", "creado_por"]
    search_fields = ["nombre", "documento", "email"]


@admin.register(Propietario)
class PropietarioAdmin(admin.ModelAdmin):
    list_display = ["nombre", "documento", "email", "telefono", "creado_por"]
    search_fields = ["nombre", "documento", "email"]


@admin.register(Inmueble)
class InmuebleAdmin(admin.ModelAdmin):
    list_display = ["titulo", "tipo", "estado", "propietario", "precio", "creado_por", "created_at"]
    list_filter = ["tipo", "estado", "creado_por"]
    search_fields = ["titulo", "direccion"]
    inlines = [FotoInmuebleInline]


class DocumentoContratoInline(admin.TabularInline):
    model = DocumentoContrato
    extra = 0
    readonly_fields = ["content_type", "size", "fecha_subida"]


@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    list_display = ["inmueble", "tipo", "estado", "inquilino_nombre", "fecha_inicio", "monto"]
    list_filter = ["tipo", "estado"]
    search_fields = ["inmueble__titulo", "inquilino_nombre"]
    inlines = [DocumentoContratoInline]


@admin.register(DocumentoContrato)
class DocumentoContratoAdmin(admin.ModelAdmin):
    list_display = ["contrato", "nombre", "fecha_subida"]
    list_filter = ["contrato__tipo"]
    search_fields = ["nombre", "contrato__inmueble__titulo"]


@admin.register(Cuota)
class CuotaAdmin(admin.ModelAdmin):
    list_display = ["descripcion", "contrato", "fecha_vencimiento", "monto", "monto_multa", "estado", "fecha_pago"]
    list_filter = ["estado", "contrato__tipo"]
    search_fields = ["descripcion", "contrato__inmueble__titulo"]
    readonly_fields = ["total"]


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ["cuota", "monto", "fecha_pago", "metodo_pago", "creado_por", "created_at"]
    list_filter = ["metodo_pago", "fecha_pago"]
    search_fields = ["cuota__descripcion", "comprobante"]
