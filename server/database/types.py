from decimal import Decimal, InvalidOperation

from sqlalchemy.types import String, TypeDecorator


class DecimalString(TypeDecorator):
    """Kwota przechowywana jako tekst, w Pythonie zawsze Decimal.

    SQLite przy typie Numeric zapisuje liczby jako float i traci precyzję,
    dlatego wartości trzymamy jako dokładny zapis dziesiętny (np. "0.00012345").
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        try:
            number = value if isinstance(value, Decimal) else Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"Nieprawidłowa kwota: {value!r}") from exc
        if not number.is_finite():
            raise ValueError(f"Nieprawidłowa kwota: {value!r}")
        return format(number.normalize(), "f")

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return Decimal(value)
