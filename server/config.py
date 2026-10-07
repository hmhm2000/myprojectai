"""Ustawienia aplikacji wczytywane z server/.env (wzór: server/.env.example)."""
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

    # Rejestracja wyłączona = działa tylko konto główne (admin) z ADMIN_USERNAME.
    allow_registration: bool
    admin_username: str
    admin_email: str
    admin_password: str

    # Ceny
    quote_currency: str
    price_ttl_seconds: int
    price_force_min_interval_seconds: int
    price_error_backoff_seconds: int
    price_http_timeout_seconds: int


def _load() -> Settings:
    secret_key = os.getenv("SECRET_KEY", "")
    if not secret_key:
        raise RuntimeError("Brak SECRET_KEY w server/.env (zobacz server/.env.example)")

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
    )


settings = _load()
