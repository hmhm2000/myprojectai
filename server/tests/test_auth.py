from dataclasses import replace

import auth
from tests.conftest import login


def test_admin_account_is_created_on_startup(client):
    headers = login(client)
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["username"] == "admin"
    assert me["is_admin"] is True


def test_wrong_password_is_rejected(client):
    response = client.post("/api/auth/login", data={"username": "admin", "password": "nope"})
    assert response.status_code == 401


def test_registration_disabled_by_default(client):
    assert client.get("/api/auth/config").json() == {"registration_enabled": False}
    response = client.post("/api/auth/register", json={
        "username": "kowalski", "email": "k@example.com", "password": "password123",
    })
    assert response.status_code == 403


def test_registration_when_enabled(client, monkeypatch):
    monkeypatch.setattr(auth, "settings", replace(auth.settings, allow_registration=True))
    assert client.get("/api/auth/config").json() == {"registration_enabled": True}

    response = client.post("/api/auth/register", json={
        "username": "kowalski", "email": "k@example.com", "password": "password123",
    })
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["username"] == "kowalski"
    assert me["is_admin"] is False

    # Zwykły użytkownik nie ma dostępu do listy użytkowników.
    assert client.get("/api/users/", headers=headers).status_code == 403


def test_admin_cannot_remove_own_admin_rights(client):
    headers = login(client)
    users = client.get("/api/users/", headers=headers).json()
    admin_id = next(u["id"] for u in users if u["username"] == "admin")
    assert client.put(f"/api/users/{admin_id}/toggle-admin", headers=headers).status_code == 400
