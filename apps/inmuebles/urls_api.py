from django.urls import path

from . import views_api

urlpatterns = [
    path("", views_api.InmuebleListCreateView.as_view(), name="api_inmueble_list_create"),
    path("disponibles/", views_api.InmuebleDisponibleListView.as_view(), name="api_inmueble_disponibles"),
    path("<int:pk>/", views_api.InmuebleRetrieveUpdateDestroyView.as_view(), name="api_inmueble_detail"),
    path("contratos/", views_api.ContratoListCreateView.as_view(), name="api_contrato_list_create"),
    path("contratos/<int:pk>/", views_api.ContratoRetrieveUpdateDestroyView.as_view(), name="api_contrato_detail"),
    path("contratos/<int:pk>/renovar/", views_api.ContratoRenovarView.as_view(), name="api_contrato_renovar"),
    path("contratos/<int:pk>/finalizar/", views_api.ContratoFinalizarView.as_view(), name="api_contrato_finalizar"),
    path("contratos/<int:pk>/rescindir/", views_api.ContratoRescindirView.as_view(), name="api_contrato_rescindir"),
    path("documentos/", views_api.DocumentoContratoCreateView.as_view(), name="api_documento_create"),
    path("cuotas/", views_api.CuotaListCreateView.as_view(), name="api_cuota_list_create"),
    path("cuotas/<int:pk>/", views_api.CuotaRetrieveUpdateDestroyView.as_view(), name="api_cuota_detail"),
    path("cuotas/<int:pk>/admin-editar/", views_api.CuotaAdminUpdateView.as_view(), name="api_cuota_admin_update"),
    path("contratos/<int:pk>/cuotas/generar/", views_api.CuotaGenerarMensualView.as_view(), name="api_cuota_generar_mensual"),
    path("pagos/", views_api.PagoListCreateView.as_view(), name="api_pago_list_create"),
    path("cuotas/<int:pk>/multa/", views_api.AplicarMultaView.as_view(), name="api_cuota_multa"),
    path("propietarios/", views_api.PropietarioListCreateView.as_view(), name="api_propietario_list_create"),
    path("propietarios/<int:pk>/", views_api.PropietarioRetrieveUpdateDestroyView.as_view(), name="api_propietario_detail"),
    path("inquilinos/", views_api.InquilinoListCreateView.as_view(), name="api_inquilino_list_create"),
    path("inquilinos/<int:pk>/", views_api.InquilinoRetrieveUpdateDestroyView.as_view(), name="api_inquilino_detail"),
    path("inquilinos/<int:pk>/contratos-activos/", views_api.InquilinoContratosActivosView.as_view(), name="api_inquilino_contratos_activos"),
]
