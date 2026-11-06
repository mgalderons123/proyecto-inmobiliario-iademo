from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inmuebles.services import (
    actualizar_cuota,
    aplicar_multa,
    finalizar_contrato,
    generar_cuota_mensual,
    registrar_pago,
    renovar_contrato,
    rescindir_contrato,
)

from .models import Contrato, Cuota, DocumentoContrato, Inmueble, Inquilino, Pago, Propietario
from .upload_validation import validate_private_upload
from .serializers import (
    AplicarMultaSerializer,
    ContratoSerializer,
    CuotaAdminUpdateSerializer,
    CuotaSerializer,
    DocumentoContratoSerializer,
    InmuebleDisponibleSerializer,
    InmuebleSerializer,
    InquilinoSerializer,
    PagoSerializer,
    PropietarioSerializer,
    RenovarContratoSerializer,
)


def _account(request):
    return getattr(request, "cuenta", None) or getattr(request._request, "cuenta", None)


class IsAccountAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user.is_superuser:
            return _account(request) is not None
        membership = getattr(request, "membership", None) or getattr(request._request, "membership", None)
        return bool(membership and membership.is_admin)

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch"
)
class PropietarioListCreateView(generics.ListCreateAPIView):
    serializer_class = PropietarioSerializer
    permission_classes = (permissions.IsAuthenticated, IsAccountAdmin)

    def get_queryset(self):
        return Propietario.objects.filter(cuenta=_account(self.request))


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch"
)
class PropietarioRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PropietarioSerializer
    permission_classes = (permissions.IsAuthenticated, IsAccountAdmin)

    def get_queryset(self):
        return Propietario.objects.filter(cuenta=_account(self.request))


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch"
)
class InquilinoListCreateView(generics.ListCreateAPIView):
    serializer_class = InquilinoSerializer
    permission_classes = (permissions.IsAuthenticated, IsAccountAdmin)

    def get_queryset(self):
        return Inquilino.objects.filter(cuenta=_account(self.request))


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch"
)
class InquilinoRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = InquilinoSerializer
    permission_classes = (permissions.IsAuthenticated, IsAccountAdmin)

    def get_queryset(self):
        return Inquilino.objects.filter(cuenta=_account(self.request))


class InquilinoContratosActivosView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsAccountAdmin)

    def get(self, request, pk):
        inquilino = generics.get_object_or_404(Inquilino, pk=pk, cuenta=_account(request))
        contratos = Contrato.objects.filter(
            inquilino_registrado=inquilino,
            estado=Contrato.Estado.ACTIVO,
        ).select_related("inmueble")
        data = [{
            "id": c.id,
            "inmueble": c.inmueble.titulo,
            "tipo": c.get_tipo_display(),
            "fecha_inicio": c.fecha_inicio.isoformat(),
            "monto": str(c.monto),
            "moneda": c.moneda,
        } for c in contratos]
        return Response({"tiene_contratos_activos": contratos.exists(), "contratos": data})


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch"
)
class InmuebleListCreateView(generics.ListCreateAPIView):
    serializer_class = InmuebleSerializer
    permission_classes = (permissions.IsAuthenticated, IsAccountAdmin)

    def get_queryset(self):
        return Inmueble.objects.filter(cuenta=_account(self.request))


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch"
)
class InmuebleRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = InmuebleSerializer
    permission_classes = (permissions.IsAuthenticated, IsAccountAdmin)

    def get_queryset(self):
        return Inmueble.objects.filter(cuenta=_account(self.request))


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch"
)
class InmuebleDisponibleListView(generics.ListAPIView):
    serializer_class = InmuebleDisponibleSerializer
    permission_classes = (permissions.IsAuthenticated, IsAccountAdmin)

    def get_queryset(self):
        return Inmueble.objects.filter(estado=Inmueble.Estado.DISPONIBLE, cuenta=_account(self.request))


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch"
)
class ContratoListCreateView(generics.ListCreateAPIView):
    serializer_class = ContratoSerializer
    permission_classes = (permissions.IsAuthenticated, IsAccountAdmin)

    def get_queryset(self):
        return Contrato.objects.filter(inmueble__cuenta=_account(self.request))


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch"
)
class ContratoRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ContratoSerializer
    permission_classes = (permissions.IsAuthenticated, IsAccountAdmin)

    def get_queryset(self):
        return Contrato.objects.filter(inmueble__cuenta=_account(self.request))


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch"
)
class ContratoRenovarView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsAccountAdmin)

    def post(self, request, pk):
        contrato = generics.get_object_or_404(
            Contrato.objects.filter(inmueble__cuenta=_account(request)), pk=pk
        )
        if contrato.estado != Contrato.Estado.ACTIVO:
            return Response({"error": "Solo se puede renovar un contrato activo."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = RenovarContratoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            nuevo = renovar_contrato(
                contrato_actual=contrato,
                fecha_inicio=data["fecha_inicio"],
                fecha_fin=data.get("fecha_fin"),
                monto=data["monto"],
                moneda=data.get("moneda") or contrato.moneda,
                comision=data.get("comision"),
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = ContratoSerializer(nuevo, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch"
)
class ContratoFinalizarView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsAccountAdmin)

    def post(self, request, pk):
        contrato = generics.get_object_or_404(
            Contrato.objects.filter(inmueble__cuenta=_account(request)), pk=pk
        )
        if contrato.estado != Contrato.Estado.ACTIVO:
            return Response({"error": "Solo se puede finalizar un contrato activo."}, status=status.HTTP_400_BAD_REQUEST)
        finalizar_contrato(contrato)
        serializer = ContratoSerializer(contrato, context={"request": request})
        return Response(serializer.data)


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch"
)
class ContratoRescindirView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsAccountAdmin)

    def post(self, request, pk):
        contrato = generics.get_object_or_404(
            Contrato.objects.filter(inmueble__cuenta=_account(request)), pk=pk
        )
        if contrato.estado != Contrato.Estado.ACTIVO:
            return Response({"error": "Solo se puede rescindir un contrato activo."}, status=status.HTTP_400_BAD_REQUEST)
        rescindir_contrato(contrato)
        serializer = ContratoSerializer(contrato, context={"request": request})
        return Response(serializer.data)


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch"
)
class DocumentoContratoCreateView(generics.CreateAPIView):
    serializer_class = DocumentoContratoSerializer
    permission_classes = (permissions.IsAuthenticated, IsAccountAdmin)

    def perform_create(self, serializer):
        contrato_id = self.request.data.get("contrato")
        contrato = generics.get_object_or_404(
            Contrato.objects.filter(inmueble__cuenta=_account(self.request)), pk=contrato_id
        )
        uploaded = self.request.FILES.get("archivo")
        if not uploaded:
            raise serializers.ValidationError({"archivo": "Se requiere un archivo."})
        try:
            validate_private_upload(uploaded)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"archivo": exc.messages}) from exc
        serializer.save(
            contrato=contrato,
            archivo=uploaded.read(),
            content_type=uploaded.content_type or "",
            size=uploaded.size,
        )


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch"
)
class CuotaListCreateView(generics.ListCreateAPIView):
    serializer_class = CuotaSerializer
    permission_classes = (permissions.IsAuthenticated, IsAccountAdmin)

    def get_queryset(self):
        qs = Cuota.objects.filter(contrato__inmueble__cuenta=_account(self.request))
        contrato_id = self.request.query_params.get("contrato")
        if contrato_id:
            qs = qs.filter(contrato_id=contrato_id)
        return qs

    def perform_create(self, serializer):
        contrato_id = self.request.data.get("contrato")
        contrato = generics.get_object_or_404(
            Contrato.objects.filter(inmueble__cuenta=_account(self.request)), pk=contrato_id
        )
        serializer.save(contrato=contrato)


class CuotaRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CuotaSerializer
    permission_classes = (permissions.IsAuthenticated, IsAccountAdmin)

    def get_queryset(self):
        return Cuota.objects.filter(contrato__inmueble__cuenta=_account(self.request))


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch"
)
class CuotaGenerarMensualView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsAccountAdmin)

    def post(self, request, pk):
        contrato = generics.get_object_or_404(
            Contrato.objects.filter(inmueble__cuenta=_account(request)), pk=pk
        )
        try:
            cuota = generar_cuota_mensual(contrato=contrato, creado_por=request.user)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = CuotaSerializer(cuota, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch"
)
class CuotaAdminUpdateView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsAccountAdmin)

    def patch(self, request, pk):
        cuota = generics.get_object_or_404(
            Cuota.objects.filter(contrato__inmueble__cuenta=_account(request)), pk=pk
        )
        serializer = CuotaAdminUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            actualizar_cuota(
                cuota,
                descripcion=serializer.validated_data.get("descripcion"),
                monto=serializer.validated_data.get("monto"),
                fecha_vencimiento=serializer.validated_data.get("fecha_vencimiento"),
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        out = CuotaSerializer(cuota, context={"request": request})
        return Response(out.data)


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch"
)
class PagoListCreateView(generics.ListCreateAPIView):
    serializer_class = PagoSerializer
    permission_classes = (permissions.IsAuthenticated, IsAccountAdmin)

    def get_queryset(self):
        qs = Pago.objects.filter(cuota__contrato__inmueble__cuenta=_account(self.request))
        cuota_id = self.request.query_params.get("cuota")
        if cuota_id:
            qs = qs.filter(cuota_id=cuota_id)
        return qs.order_by("-fecha_pago", "-created_at")


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch"
)
class AplicarMultaView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsAccountAdmin)

    def post(self, request, pk):
        cuota = generics.get_object_or_404(
            Cuota.objects.filter(contrato__inmueble__cuenta=_account(request)), pk=pk
        )
        serializer = AplicarMultaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            aplicar_multa(
                cuota=cuota,
                monto_fijo=serializer.validated_data.get("monto_fijo"),
                porcentaje=serializer.validated_data.get("porcentaje"),
                motivo=serializer.validated_data.get("motivo", ""),
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        cuota_serializer = CuotaSerializer(cuota, context={"request": request})
        return Response(cuota_serializer.data)
