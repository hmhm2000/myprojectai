# Import every model so that Base.metadata (and Alembic) see all tables.
from models.user import User  # noqa: F401
from models.portfolio import Portfolio, Position, Sale  # noqa: F401
from models.favorites import FavoriteList, FavoriteCoin  # noqa: F401
from models.alerts import Alert, AlertEvent  # noqa: F401
from models.chart_indicators import ChartIndicator  # noqa: F401
