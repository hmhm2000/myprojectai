from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

# Decimal w JSON zawsze jako string w zapisie dziesiętnym ("0.00000001", nie "1E-8").
Amount = Annotated[Decimal, PlainSerializer(lambda d: format(d, "f"), return_type=str, when_used="json")]
