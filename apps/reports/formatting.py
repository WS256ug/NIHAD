"""Display report numbers without changing stored values or precision."""
from decimal import Decimal, InvalidOperation


def report_number(value):
    if value is None:
        return "-"
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    if not number.is_finite():
        return str(value)
    text = format(number, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text
