from django.contrib import admin, messages
from django.utils import timezone

from .models import Cuenta, MembresiaCuenta
from .plans import approve_plan_change


@admin.register(Cuenta)
class CuentaAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "plan",
        "plan_solicitado",
        "uso_inquilinos",
        "activa",
    )
    list_filter = ("plan", "plan_solicitado", "activa")
    search_fields = ("nombre",)
    readonly_fields = (
        "uso_inquilinos",
        "plan_solicitado_por",
        "plan_solicitado_at",
        "plan_aprobado_por",
        "plan_aprobado_at",
    )
    actions = ("aprobar_plan_solicitado",)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("inquilinos")

    @admin.display(description="Uso")
    def uso_inquilinos(self, obj):
        return f"{obj.inquilinos_utilizados} / {obj.limite_inquilinos}"

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        if change and "plan" in form.changed_data:
            obj.plan_aprobado_por = request.user
            obj.plan_aprobado_at = timezone.now()
            obj.plan_solicitado = ""
            obj.plan_solicitado_por = None
            obj.plan_solicitado_at = None
        super().save_model(request, obj, form, change)

    @admin.action(description="Aprobar el plan solicitado")
    def aprobar_plan_solicitado(self, request, queryset):
        approved = 0
        for account in queryset:
            if not account.plan_solicitado:
                continue
            try:
                approve_plan_change(account, request.user)
            except ValueError as exc:
                self.message_user(request, f"{account}: {exc}", level=messages.ERROR)
            else:
                approved += 1
        if approved:
            self.message_user(request, f"Planes aprobados: {approved}.")


@admin.register(MembresiaCuenta)
class MembresiaCuentaAdmin(admin.ModelAdmin):
    list_display = ("cuenta", "user", "rol", "activa")
    list_filter = ("rol", "activa")
    search_fields = ("cuenta__nombre", "user__username", "user__email")

    def has_module_permission(self, request):
        return request.user.is_superuser
