from dataclasses import replace

import auth
from tests.conftest import login


def names(items, pinned=None):
    return [i["name"] for i in items if pinned is None or i["pinned"] == pinned]


def test_chart_intervals_per_user(client, monkeypatch):
    headers = login(client)
    items = client.get("/api/chart-intervals", headers=headers).json()
    assert names(items) == ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"]
    assert all(i["pinned"] and not i["custom"] for i in items)

    items = client.post("/api/chart-intervals", json={"name": "3D"}, headers=headers).json()
    items = client.post("/api/chart-intervals", json={"name": "2W"}, headers=headers).json()
    assert names(items) == ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "3d", "1w", "2w", "1M"]   # sorted by length
    assert [i for i in items if i["name"] == "3d"][0] == {"name": "3d", "custom": True, "pinned": True}

    items = client.put("/api/chart-intervals/1m", json={"pinned": False}, headers=headers).json()
    items = client.put("/api/chart-intervals/3d", json={"pinned": False}, headers=headers).json()
    assert names(items, pinned=False) == ["1m", "3d"]        # still on the list, just not a button
    items = client.post("/api/chart-intervals", json={"name": "3d"}, headers=headers).json()
    assert names(items, pinned=False) == ["1m"]              # adding again pins it, no duplicate
    assert names(items).count("3d") == 1

    assert client.post("/api/chart-intervals", json={"name": "2x"}, headers=headers).json()["code"] == "candles.invalid_interval"
    assert client.delete("/api/chart-intervals/1h", headers=headers).status_code == 404     # presets can't be removed
    assert client.delete("/api/chart-intervals/2w", headers=headers).status_code == 204
    assert "2w" not in names(client.get("/api/chart-intervals", headers=headers).json())

    monkeypatch.setattr(auth, "settings", replace(auth.settings, allow_registration=True))
    token = client.post("/api/auth/register", json={"username": "other", "email": "o@example.com",
                                                    "password": "password123"}).json()["access_token"]
    other = {"Authorization": f"Bearer {token}"}
    assert "3d" not in names(client.get("/api/chart-intervals", headers=other).json())
    assert client.delete("/api/chart-intervals/3d", headers=other).status_code == 404
