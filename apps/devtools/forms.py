from django import forms
from django.utils.translation import gettext_lazy as _


class FormCatalogForm(forms.Form):
    nombre = forms.CharField(label=_("Nombre completo"), help_text=_("Como figura en el documento."))
    email = forms.EmailField(label=_("Correo electrónico"), required=False)
    tipo = forms.ChoiceField(
        label=_("Tipo de contacto"),
        choices=(("tenant", _("Inquilino")), ("owner", _("Propietario"))),
        widget=forms.RadioSelect,
    )
    activo = forms.BooleanField(label=_("Contacto activo"), required=False)
    documento = forms.FileField(label=_("Documento adjunto"), required=False)
    notas = forms.CharField(label=_("Notas"), required=False, widget=forms.Textarea)
    referencia = forms.CharField(
        label=_("Referencia interna"),
        required=False,
        initial="CR-2026-0042",
        disabled=True,
    )
