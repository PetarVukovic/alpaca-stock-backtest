"""Exact decimal wire/storage values. Floats are only presentation/market analytics."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN

ZERO = Decimal('0')


def decimal(value) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError('Nevaljan decimalni iznos.') from exc
    if not result.is_finite():
        raise ValueError('Iznos mora biti konačan broj.')
    return result


def text(value) -> str:
    return format(decimal(value), 'f')


def cents(value) -> str:
    return format(decimal(value).quantize(Decimal('.01'), rounding=ROUND_HALF_EVEN), 'f')
