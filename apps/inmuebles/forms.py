from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Contrato, Cuota, FotoInmueble, Inmueble, Inquilino, Pago, Propietario
from .upload_validation import validate_private_upload


class ContactForm(forms.ModelForm):
    class Meta:
        fields = ["nombre", "email", "telefono", "documento", "direccion", "notas"]
        labels = {
            "nombre": _("Nombre completo"),
            "email": _("Correo electrónico"),
            "telefono": _("Teléfono"),
            "documento": _("Documento"),
            "direccion": _("Dirección"),
            "notas": _("Notas"),
        }
        widgets = {
            "nombre": forms.TextInput(attrs={"autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "telefono": forms.TextInput(attrs={"autocomplete": "tel"}),
            "notas": forms.Textarea(attrs={"rows": 3}),
            "direccion": forms.Textarea(attrs={"rows": 2, "autocomplete": "street-address"}),
        }
        help_texts = {
            "nombre": _("Ingresá el nombre completo tal como figura en su documentación."),
        }


class InquilinoForm(ContactForm):
    class Meta(ContactForm.Meta):
        model = Inquilino


class PropietarioForm(ContactForm):
    class Meta(ContactForm.Meta):
        model = Propietario


class InmuebleForm(forms.ModelForm):
    estado = forms.ChoiceField(choices=Inmueble.Estado.choices, required=False)
    tipo_alquiler = forms.ChoiceField(choices=Inmueble.TipoAlquiler.choices, required=False)
    latitud = forms.DecimalField(required=False, widget=forms.HiddenInput(attrs={"id": "id_latitud"}))
    longitud = forms.DecimalField(required=False, widget=forms.HiddenInput(attrs={"id": "id_longitud"}))

    class Meta:
        model = Inmueble
        fields = [
            "titulo", "direccion", "descripcion", "precio", "moneda", "tipo",
            "estado", "propietario", "superficie", "habitaciones", "banos",
            "tipo_alquiler", "latitud", "longitud",
        ]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, user=None, cuenta=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["moneda"].required = False
        if not cuenta and user:
            from apps.users.accounts import ensure_account_for_user

            cuenta = ensure_account_for_user(user)
        if cuenta:
            self.fields["propietario"].queryset = Propietario.objects.filter(cuenta=cuenta)
            self.fields["moneda"].initial = cuenta.moneda_predeterminada

    def clean_moneda(self):
        return self.cleaned_data.get("moneda") or self.fields["moneda"].initial or "USD"

    def clean_precio(self):
        precio = self.cleaned_data.get("precio")
        if precio is not None and precio < 0:
            raise forms.ValidationError("El precio no puede ser negativo.")
        return precio


class FotoInmuebleForm(forms.ModelForm):
    class Meta:
        model = FotoInmueble
        fields = ["imagen", "orden"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["imagen"].required = False
        self.fields["orden"].required = False


FotoInmuebleFormSet = forms.inlineformset_factory(
    Inmueble, FotoInmueble, form=FotoInmuebleForm,
    extra=3, max_num=10, can_delete=True,
)


class ContratoForm(forms.ModelForm):
    class Meta:
        model = Contrato
        fields = [
            "tipo", "inquilino_registrado", "frecuencia_pago", "duracion_anos",
            "fecha_inicio", "fecha_fin", "monto", "moneda", "comision", "garantia",
        ]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
            "frecuencia_pago": forms.Select(),
            "duracion_anos": forms.NumberInput(attrs={"min": 1}),
        }

    def __init__(self, *args, user=None, cuenta=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["moneda"].required = False
        if not cuenta and user:
            from apps.users.accounts import ensure_account_for_user

            cuenta = ensure_account_for_user(user)
        if cuenta:
            self.fields["inquilino_registrado"].queryset = Inquilino.objects.filter(cuenta=cuenta)
            self.fields["moneda"].initial = cuenta.moneda_predeterminada

    def clean_moneda(self):
        return self.cleaned_data.get("moneda") or self.fields["moneda"].initial or "USD"

    def clean(self):
        cleaned_data = super().clean()
        if (
            cleaned_data.get("tipo") == Contrato.Tipo.ALQUILER
            and not cleaned_data.get("inquilino_registrado")
        ):
            self.add_error(
                "inquilino_registrado",
                "Los contratos de alquiler requieren un inquilino registrado.",
            )
        return cleaned_data


class RenovarContratoForm(forms.Form):
    fecha_inicio = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    fecha_fin = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), required=False)
    monto = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    moneda = forms.ChoiceField(choices=Inmueble._meta.get_field("moneda").choices, required=False)
    comision = forms.DecimalField(max_digits=12, decimal_places=2, required=False)


class CuotaPersonalizadaForm(forms.Form):
    monto = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0.01, label="Monto")
    descripcion = forms.CharField(max_length=200, label="Descripción")
    fecha_vencimiento = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Fecha de vencimiento",
    )


class PagoForm(forms.Form):
    monto = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0.01, label="Monto")
    fecha_pago = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Fecha de pago",
    )
    metodo_pago = forms.ChoiceField(choices=Pago.Metodo.choices, label="Método de pago")
    archivo_comprobante = forms.FileField(required=False, label="Comprobante (archivo)")
    comprobante = forms.CharField(max_length=100, required=False, label="Referencia del comprobante")
    observaciones = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}), required=False, label="Observaciones",
    )

    def clean_archivo_comprobante(self):
        upload = self.cleaned_data.get("archivo_comprobante")
        return validate_private_upload(upload) if upload else None


class AprobarPagoForm(forms.Form):
    accion = forms.ChoiceField(choices=[("aprobar", "Aprobar"), ("rechazar", "Rechazar")], widget=forms.RadioSelect)
    motivo_rechazo = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Motivo del rechazo (obligatorio si se rechaza)"}),
        required=False, label="Motivo del rechazo",
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("accion") == "rechazar" and not cleaned_data.get("motivo_rechazo"):
            raise forms.ValidationError("Debe indicar un motivo para rechazar el pago.")
        return cleaned_data


class CuotaEditForm(forms.ModelForm):
    class Meta:
        model = Cuota
        fields = ["descripcion", "monto", "fecha_vencimiento"]
        widgets = {
            "fecha_vencimiento": forms.DateInput(attrs={"type": "date"}),
        }


class MultaForm(forms.Form):
    monto_fijo = forms.DecimalField(
        max_digits=12, decimal_places=2, required=False, label="Monto fijo",
    )
    porcentaje = forms.DecimalField(
        max_digits=5, decimal_places=2, required=False, label="Porcentaje (%)",
    )
    motivo = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}), required=False, label="Motivo",
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("monto_fijo") is None and cleaned_data.get("porcentaje") is None:
            raise forms.ValidationError("Debe indicar un monto fijo o un porcentaje.")
        return cleaned_data


class MultaEditForm(forms.ModelForm):
    class Meta:
        model = Cuota
        fields = ["monto_multa"]
