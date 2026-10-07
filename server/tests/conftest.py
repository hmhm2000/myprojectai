import os
import sys
import tempfile
from pathlib import Path

import pytest

# Separate database and test settings - must be set before config is imported.
_tmp_dir = tempfile.mkdtemp(prefix="wallet_tests_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp_dir, 'test.db').as_posix()}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin-password"
os.environ["ALLOW_REGISTRATION"] = "false"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models  # noqa: E402,F401
from database.db import Base, engine  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


# Modules that import the global price_service - replaced with a fake one in tests.
PRICE_SERVICE_USERS = ["main", "api.routes.prices", "api.routes.portfolios"]


@pytest.fixture
def fake_prices(monkeypatch):
    import importlib
    from types import SimpleNamespace

    from tests.fakes import FakeClock, FakeProvider, make_service

    clock = FakeClock()
    okx = FakeProvider("okx", {"BTC": "60000", "ETH": "2500"})
    bybit = FakeProvider("bybit", {"BTC": "60010", "SPX": "0.5"})
    service = make_service(clock, okx, bybit)
    for module_name in PRICE_SERVICE_USERS:
        monkeypatch.setattr(importlib.import_module(module_name), "price_service", service)
    return SimpleNamespace(service=service, clock=clock, okx=okx, bybit=bybit)


@pytest.fixture
def client(fake_prices):
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as test_client:  # runs the lifespan (creates the admin account)
        yield test_client


def login(client, username="admin", password="admin-password") -> dict:
    response = client.post("/api/auth/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
