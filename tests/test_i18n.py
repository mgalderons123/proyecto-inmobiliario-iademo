from django.utils import translation
from django.utils.translation import gettext


def test_english_catalog_contains_operational_ui():
    with translation.override("en"):
        assert gettext("Crear inmueble") == "Create property"
        assert gettext("Pagos Pendientes de Aprobación") == "Payments Awaiting Approval"


def test_portuguese_catalog_contains_operational_ui():
    with translation.override("pt"):
        assert gettext("Crear inmueble") == "Criar imóvel"
        assert gettext("Pagos Pendientes de Aprobación") == "Pagamentos Pendentes de Aprovação"
