"""Application settings loaded from server/.env (template: server/.env.example)."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def _list(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    secret_key: str
    access_token_expire_minutes: int
    database_url: str
    cors_origins: list[str]

    # Registration disabled = only the main (admin) account from ADMIN_USERNAME can log in.
    allow_registration: bool
    admin_username: str
    admin_email: str
    admin_password: str

    # Prices
    quote_currency: str
    price_ttl_seconds: int
    price_force_min_interval_seconds: int
    price_error_backoff_seconds: int
    price_http_timeout_seconds: int

    # Time zone of dates entered in the UI (bought_at/sold_at are stored as local time).
    user_timezone: str

    # Alerts: seconds between checks (0 = checker disabled, e.g. in tests).
    alert_check_seconds: int

    # Import of exchange exports: folder with the CSV files, import at start-up, account they belong to.
    import_dir: Path
    import_on_startup: bool
    import_username: str


def _load() -> Settings:
    secret_key = os.getenv("SECRET_KEY", "")
    if not secret_key:
        raise RuntimeError("SECRET_KEY is missing in server/.env (see server/.env.example)")
    if len(secret_key) < 32:
        raise RuntimeError("SECRET_KEY is too short - use at least 32 random characters (see server/.env.example)")

    default_db = f"sqlite:///{(BASE_DIR / 'db' / 'database.db').as_posix()}"

    return Settings(
        secret_key=secret_key,
        access_token_expire_minutes=_int("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24 * 7),
        database_url=os.getenv("DATABASE_URL") or default_db,
        cors_origins=_list("CORS_ORIGINS", "http://localhost:3000"),
        allow_registration=_bool("ALLOW_REGISTRATION", False),
        admin_username=os.getenv("ADMIN_USERNAME", "admin").strip(),
        admin_email=os.getenv("ADMIN_EMAIL", "admin@example.com").strip(),
        admin_password=os.getenv("ADMIN_PASSWORD", ""),
        quote_currency=os.getenv("QUOTE_CURRENCY", "USDT").strip().upper(),
        price_ttl_seconds=_int("PRICE_TTL_SECONDS", 180),
        price_force_min_interval_seconds=_int("PRICE_FORCE_MIN_INTERVAL_SECONDS", 10),
        price_error_backoff_seconds=_int("PRICE_ERROR_BACKOFF_SECONDS", 30),
        price_http_timeout_seconds=_int("PRICE_HTTP_TIMEOUT_SECONDS", 10),
        user_timezone=os.getenv("USER_TIMEZONE", "Europe/Warsaw").strip(),
        alert_check_seconds=_int("ALERT_CHECK_SECONDS", 60),
        import_dir=Path(os.getenv("IMPORT_DIR") or BASE_DIR.parent / "data" / "imports" / "okx"),
        import_on_startup=_bool("IMPORT_ON_STARTUP", True),
        import_username=(os.getenv("IMPORT_USERNAME") or os.getenv("ADMIN_USERNAME") or "admin").strip(),
    )


settings = _load()
