from decimal import Decimal

from rest_framework import serializers, status

from apps.inmuebles.services import (
    ContratoError,
    CuotaError,
    InmuebleError,
    InquilinoError,
    PagoError,
    PropietarioError,
    TenantLimitReached,
    actualizar_contrato,
    actualizar_cuota,
    actualizar_inmueble,
    actualizar_inquilino,
    actualizar_propietario,
    aplicar_multa,
    crear_contrato,
    crear_cuota_personalizada,
    crear_inmueble,
    crear_inquilino,
    crear_propietario,
    generar_cuota_mensual,
    registrar_pago,
)

from .models import Contrato, Cuota, DocumentoContrato, FotoInmueble, Inmueble, Inquilino, Pago, Propietario


def _request_account(serializer):
    request = serializer.context["request"]
    account = getattr(request, "cuenta", None)
    if account is None and hasattr(request, "_request"):
        account = getattr(request._request, "cuenta", None)
    return account


class InquilinoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Inquilino
        fields = [
            "id", "nombre", "email", "telefono", "documento",
            "direccion", "notas", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def create(self, validated_data):
        try:
            return crear_inquilino(
                nombre=validated_data["nombre"],
                creado_por=self.context["request"].user,
                cuenta=_request_account(self),
                email=validated_data.get("email", ""),
                telefono=validated_data.get("telefono", ""),
                documento=validated_data.get("documento", ""),
                direccion=validated_data.get("direccion", ""),
                notas=validated_data.get("notas", ""),
            )
        except TenantLimitReached as e:
            from rest_framework.exceptions import APIException

            error = APIException(e.message, code="tenant_limit_reached")
            error.status_code = status.HTTP_409_CONFLICT
            raise error
        except InquilinoError as e:
            raise serializers.ValidationError({e.field or "non_field_errors": e.message})

    def update(self, instance, validated_data):
        try:
            return actualizar_inquilino(
                instance,
                nombre=validated_data.get("nombre"),
                email=validated_data.get("email"),
                telefono=validated_data.get("telefono"),
                documento=validated_data.get("documento"),
                direccion=validated_data.get("direccion"),
                notas=validated_data.get("notas"),
            )
        except InquilinoError as e:
            raise serializers.ValidationError({e.field: e.message})


class PropietarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Propietario
        fields = [
            "id", "nombre", "email", "telefono", "documento",
            "direccion", "notas", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def create(self, validated_data):
        try:
            return crear_propietario(
                nombre=validated_data["nombre"],
                creado_por=self.context["request"].user,
                cuenta=_request_account(self),
                email=validated_data.get("email", ""),
                telefono=validated_data.get("telefono", ""),
                documento=validated_data.get("documento", ""),
                direccion=validated_data.get("direccion", ""),
                notas=validated_data.get("notas", ""),
            )
        except PropietarioError as e:
            raise serializers.ValidationError({e.field: e.message})

    def update(self, instance, validated_data):
        try:
            return actualizar_propietario(
                instance,
                nombre=validated_data.get("nombre"),
                email=validated_data.get("email"),
                telefono=validated_data.get("telefono"),
                documento=validated_data.get("documento"),
                direccion=validated_data.get("direccion"),
                notas=validated_data.get("notas"),
            )
        except PropietarioError as e:
            raise serializers.ValidationError({e.field: e.message})


class FotoInmuebleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FotoInmueble
        fields = ["id", "imagen", "orden"]


class InmuebleSerializer(serializers.ModelSerializer):
    fotos = FotoInmuebleSerializer(many=True, read_only=True)
    estado = serializers.CharField(default=Inmueble.Estado.DISPONIBLE)

    class Meta:
        model = Inmueble
        fields = [
            "id", "titulo", "direccion", "descripcion", "precio", "moneda", "tipo", "estado",
            "propietario", "superficie", "habitaciones", "banos", "latitud", "longitud",
            "direccion_normalizada", "fotos", "created_at", "updated_at",
        ]
        read_only_fields = ["latitud", "longitud", "direccion_normalizada", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        account = _request_account(self)
        if account:
            self.fields["propietario"].queryset = Propietario.objects.filter(cuenta=account)

    def create(self, validated_data):
        try:
            return crear_inmueble(
                titulo=validated_data["titulo"],
                direccion=validated_data["direccion"],
                creado_por=self.context["request"].user,
                cuenta=_request_account(self),
                descripcion=validated_data.get("descripcion", ""),
                precio=validated_data.get("precio"),
                moneda=validated_data.get("moneda"),
                tipo=validated_data.get("tipo", Inmueble.Tipo.OTRO),
                estado=validated_data.get("estado", Inmueble.Estado.DISPONIBLE),
                propietario=validated_data.get("propietario"),
                superficie=validated_data.get("superficie"),
                habitaciones=validated_data.get("habitaciones"),
                banos=validated_data.get("banos"),
            )
        except InmuebleError as e:
            raise serializers.ValidationError({e.field: e.message})

    def update(self, instance, validated_data):
        try:
            return actualizar_inmueble(
                instance,
                titulo=validated_data.get("titulo"),
                direccion=validated_data.get("direccion"),
                descripcion=validated_data.get("descripcion"),
                precio=validated_data.get("precio"),
                moneda=validated_data.get("moneda"),
                tipo=validated_data.get("tipo"),
                estado=validated_data.get("estado"),
                propietario=validated_data.get("propietario"),
                superficie=validated_data.get("superficie"),
                habitaciones=validated_data.get("habitaciones"),
                banos=validated_data.get("banos"),
            )
        except InmuebleError as e:
            raise serializers.ValidationError({e.field: e.message})


class InmuebleDisponibleSerializer(serializers.ModelSerializer):
    fotos = FotoInmuebleSerializer(many=True, read_only=True)

    class Meta:
        model = Inmueble
        fields = [
            "id", "titulo", "direccion", "descripcion", "precio", "moneda", "tipo",
            "superficie", "habitaciones", "banos", "fotos",
        ]


class ContratoSerializer(serializers.ModelSerializer):
    inmueble_titulo = serializers.CharField(source="inmueble.titulo", read_only=True)
    inquilino_registrado_nombre = serializers.CharField(source="inquilino_registrado.nombre", read_only=True)

    class Meta:
        model = Contrato
        fields = [
            "id", "inmueble", "inmueble_titulo", "tipo", "estado",
            "inquilino", "inquilino_registrado", "inquilino_registrado_nombre",
            "inquilino_nombre", "inquilino_email", "inquilino_telefono",
            "frecuencia_pago", "duracion_anos",
            "fecha_inicio", "fecha_fin", "monto", "moneda", "comision", "garantia",
            "fecha_finalizacion", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "estado", "fecha_finalizacion"]
        extra_kwargs = {
            "inquilino": {"read_only": True},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        account = _request_account(self)
        if account:
            self.fields["inmueble"].queryset = Inmueble.objects.filter(cuenta=account)
            self.fields["inquilino_registrado"].queryset = Inquilino.objects.filter(cuenta=account)

    def create(self, validated_data):
        inmueble = validated_data["inmueble"]
        if inmueble.cuenta_id != _request_account(self).id:
            raise serializers.ValidationError({"inmueble": "No tiene permiso para crear contratos en este inmueble."})
        try:
            return crear_contrato(
                inmueble=inmueble,
                tipo=validated_data["tipo"],
                creado_por=self.context["request"].user,
                inquilino=validated_data.get("inquilino"),
                inquilino_registrado=validated_data.get("inquilino_registrado"),
                inquilino_nombre=validated_data.get("inquilino_nombre", ""),
                inquilino_email=validated_data.get("inquilino_email", ""),
                inquilino_telefono=validated_data.get("inquilino_telefono", ""),
                frecuencia_pago=validated_data.get("frecuencia_pago", Contrato.FrecuenciaPago.MENSUAL),
                duracion_anos=validated_data.get("duracion_anos"),
                fecha_inicio=validated_data["fecha_inicio"],
                fecha_fin=validated_data.get("fecha_fin"),
                monto=validated_data["monto"],
                moneda=validated_data.get("moneda"),
                comision=validated_data.get("comision"),
                garantia=validated_data.get("garantia"),
            )
        except TenantLimitReached as e:
            from rest_framework.exceptions import APIException

            error = APIException(e.message, code="tenant_limit_reached")
            error.status_code = status.HTTP_409_CONFLICT
            raise error
        except ContratoError as e:
            raise serializers.ValidationError({e.field: e.message})

    def update(self, instance, validated_data):
        try:
            return actualizar_contrato(
                instance,
                tipo=validated_data.get("tipo"),
                inquilino=validated_data.get("inquilino"),
                inquilino_registrado=validated_data.get("inquilino_registrado"),
                inquilino_nombre=validated_data.get("inquilino_nombre"),
                inquilino_email=validated_data.get("inquilino_email"),
                inquilino_telefono=validated_data.get("inquilino_telefono"),
                frecuencia_pago=validated_data.get("frecuencia_pago"),
                duracion_anos=validated_data.get("duracion_anos"),
                fecha_inicio=validated_data.get("fecha_inicio"),
                fecha_fin=validated_data.get("fecha_fin"),
                monto=validated_data.get("monto"),
                moneda=validated_data.get("moneda"),
                comision=validated_data.get("comision"),
                garantia=validated_data.get("garantia"),
            )
        except ContratoError as e:
            raise serializers.ValidationError({e.field: e.message})


class DocumentoContratoSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentoContrato
        fields = ["id", "contrato", "nombre", "content_type", "size", "fecha_subida"]
        read_only_fields = ["content_type", "size", "fecha_subida"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        account = _request_account(self)
        if account:
            self.fields["contrato"].queryset = Contrato.objects.filter(inmueble__cuenta=account)


class CuotaSerializer(serializers.ModelSerializer):
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    contrato_titulo = serializers.CharField(source="contrato.inmueble.titulo", read_only=True)
    moneda = serializers.CharField(read_only=True)

    class Meta:
        model = Cuota
        fields = [
            "id", "contrato", "contrato_titulo", "numero", "descripcion",
            "fecha_vencimiento", "monto", "moneda", "monto_multa", "total",
            "estado", "fecha_pago", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "estado", "fecha_pago"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        account = _request_account(self)
        if account:
            self.fields["contrato"].queryset = Contrato.objects.filter(inmueble__cuenta=account)

    def update(self, instance, validated_data):
        # Structural changes would move existing payments to another contract.
        if any(key in validated_data for key in ("contrato", "numero", "monto_multa")):
            raise serializers.ValidationError(
                "Contrato, número y multa se modifican mediante operaciones específicas."
            )
        try:
            return actualizar_cuota(instance, **validated_data)
        except CuotaError as exc:
            raise serializers.ValidationError({exc.field: exc.message})


class PagoSerializer(serializers.ModelSerializer):
    moneda = serializers.CharField(read_only=True)
    class Meta:
        model = Pago
        fields = [
            "id", "cuota", "monto", "moneda", "fecha_pago", "metodo_pago",
            "comprobante", "observaciones", "creado_por", "created_at",
        ]
        read_only_fields = ["created_at", "creado_por"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        account = _request_account(self)
        if account:
            self.fields["cuota"].queryset = Cuota.objects.filter(contrato__inmueble__cuenta=account)

    def create(self, validated_data):
        cuota = validated_data["cuota"]
        if cuota.contrato.inmueble.cuenta_id != _request_account(self).id:
            raise serializers.ValidationError({"cuota": "No tiene permiso para registrar pagos en esta cuota."})
        try:
            return registrar_pago(
                cuota=cuota,
                monto=validated_data["monto"],
                fecha_pago=validated_data["fecha_pago"],
                metodo_pago=validated_data["metodo_pago"],
                creado_por=self.context["request"].user,
                comprobante=validated_data.get("comprobante", ""),
                observaciones=validated_data.get("observaciones", ""),
            )
        except PagoError as e:
            raise serializers.ValidationError({e.field: e.message})


class CuotaAdminUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cuota
        fields = ["descripcion", "monto", "fecha_vencimiento"]


class AplicarMultaSerializer(serializers.Serializer):
    monto_fijo = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    porcentaje = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    motivo = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        if data.get("monto_fijo") is None and data.get("porcentaje") is None:
            raise serializers.ValidationError("Debe indicar un monto fijo o un porcentaje.")
        if data.get("monto_fijo") is not None and data["monto_fijo"] <= 0:
            raise serializers.ValidationError({"monto_fijo": "El monto debe ser mayor a cero."})
        if data.get("porcentaje") and data["porcentaje"] <= 0:
            raise serializers.ValidationError({"porcentaje": "El porcentaje debe ser mayor a cero."})
        return data


class RenovarContratoSerializer(serializers.Serializer):
    fecha_inicio = serializers.DateField()
    fecha_fin = serializers.DateField(required=False, allow_null=True)
    monto = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    moneda = serializers.ChoiceField(choices=Inmueble._meta.get_field("moneda").choices, required=False)
    comision = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)

    def validate(self, data):
        if data.get("fecha_fin") and data["fecha_fin"] < data["fecha_inicio"]:
            raise serializers.ValidationError({"fecha_fin": "No puede ser anterior a la fecha de inicio."})
        return data
