from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import render

from .forms import FormCatalogForm


@staff_member_required
def form_catalog(request):
    if not settings.DEBUG:
        raise Http404

    invalid_form = FormCatalogForm(
        data={
            "nombre": "",
            "email": "correo-invalido",
            "tipo": "tenant",
            "activo": "on",
            "notas": "Ejemplo de un formulario enviado con errores.",
        },
        prefix="invalid",
    )
    invalid_form.is_valid()
    return render(
        request,
        "devtools/form_catalog.html",
        {
            "empty_form": FormCatalogForm(prefix="empty"),
            "invalid_form": invalid_form,
            "filled_form": FormCatalogForm(
                initial={
                    "nombre": "Alex Morgan",
                    "email": "alex@example.test",
                    "tipo": "owner",
                    "activo": True,
                    "notas": "Prefiere comunicaciones por correo electrónico.",
                },
                prefix="filled",
            ),
        },
    )
