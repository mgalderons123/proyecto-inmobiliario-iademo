from decimal import Decimal

from django.utils.formats import number_format


CURRENCY_CHOICES = (
    ("USD", "USD - Dólar estadounidense"),
    ("ARS", "ARS - Peso argentino"),
    ("BOB", "BOB - Boliviano"),
    ("BRL", "BRL - Real brasileño"),
    ("CLP", "CLP - Peso chileno"),
    ("COP", "COP - Peso colombiano"),
    ("CRC", "CRC - Colón costarricense"),
    ("CUP", "CUP - Peso cubano"),
    ("DOP", "DOP - Peso dominicano"),
    ("GTQ", "GTQ - Quetzal guatemalteco"),
    ("HTG", "HTG - Gourde haitiano"),
    ("HNL", "HNL - Lempira hondureño"),
    ("MXN", "MXN - Peso mexicano"),
    ("NIO", "NIO - Córdoba nicaragüense"),
    ("PAB", "PAB - Balboa panameño"),
    ("PEN", "PEN - Sol peruano"),
    ("PYG", "PYG - Guaraní paraguayo"),
    ("UYU", "UYU - Peso uruguayo"),
    ("VES", "VES - Bolívar venezolano"),
)

CURRENCY_CODES = frozenset(code for code, _ in CURRENCY_CHOICES)
ZERO_DECIMAL_CURRENCIES = frozenset({"CLP", "PYG"})


def format_money(value, currency="USD"):
    """Return an unambiguous, localized monetary value."""
    code = currency if currency in CURRENCY_CODES else "USD"
    amount = Decimal(value or 0)
    decimal_pos = 0 if code in ZERO_DECIMAL_CURRENCIES else 2
    return f"{code} {number_format(amount, decimal_pos=decimal_pos, use_l10n=True, force_grouping=True)}"
