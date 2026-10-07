# Import wszystkich modeli, żeby Base.metadata (i Alembic) widziały komplet tabel.
from models.user import User  # noqa: F401
from models.portfolio import Portfolio, Position, Sale  # noqa: F401
from models.favorites import FavoriteList, FavoriteCoin  # noqa: F401
