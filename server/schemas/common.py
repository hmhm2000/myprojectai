from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

# Decimals are always serialized to JSON as plain decimal strings ("0.00000001", not "1E-8").
Amount = Annotated[Decimal, PlainSerializer(lambda d: format(d, "f"), return_type=str, when_used="json")]
