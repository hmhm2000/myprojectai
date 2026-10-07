from decimal import Decimal, InvalidOperation

from sqlalchemy.types import String, TypeDecorator


class DecimalString(TypeDecorator):
    """Amount stored as text, always a Decimal in Python.

    SQLite stores Numeric columns as floats and loses precision,
    so values are kept as an exact decimal string (e.g. "0.00012345").
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        try:
            number = value if isinstance(value, Decimal) else Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"Invalid amount: {value!r}") from exc
        if not number.is_finite():
            raise ValueError(f"Invalid amount: {value!r}")
        return format(number.normalize(), "f")

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return Decimal(value)
