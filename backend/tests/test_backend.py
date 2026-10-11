import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import advisory, config, main, model, risk, weather  # noqa: E402

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def no_key_no_cache(monkeypatch):
    """Hermetic: never use a real key from backend/.env, never reuse cached weather."""
    monkeypatch.setattr(config, "OWM_API_KEY", "")
    weather._cache.clear()
SAMPLES = config.ROOT / "data" / "plantdoc_samples"


def jpeg_bytes(size=(300, 300), color=(60, 140, 60), fmt="JPEG"):
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, fmt)
    return b.getvalue()


def assess(mode):
    return risk.assess(weather.demo_series(mode))


def test_health():
    r = client.get("/api/health").json()
    assert r["status"] == "ok" and r["model"]["available"] is True and r["model"]["num_classes"] == 38


def test_scenarios_bounds_and_factor_sums():
    for mode in ("normal", "conducive"):
        a = assess(mode)
        assert a["status"] == "ok" and 0 <= a["index"] <= 100
        assert a["index"] == round(sum(f["points"] for f in a["factors"]), 1)
        assert all(0 <= f["points"] <= f["max_points"] for f in a["factors"])
        assert all(0 <= t["index"] <= 100 for t in a["trend"]) and len(a["trend"]) > 24
    n, c = assess("normal"), assess("conducive")
    assert n["category"] == "Low" and c["category"] in ("High", "Very High") and c["index"] > n["index"] + 40


def test_missing_values_not_zero_filled():
    pts = weather.demo_series("conducive")
    for p in pts[:2]:
        p["rh"] = None  # missing, must be skipped (not treated as 0%)
    a = risk.assess(pts)
    assert a["status"] == "ok" and a["factors"][2]["detail"].startswith("Mean RH 9")
    for p in pts:
        p["rain_mm"] = None
    a2 = risk.assess(pts)
    assert a2["factors"][3]["available"] is False
    for p in pts:
        p["temp_c"] = None
    assert risk.assess(pts)["status"] == "unavailable"


def test_forecast_endpoint_scenarios_change_everything():
    n = client.post("/api/v1/risk/forecast", json={"farm_id": 1, "mode": "normal"}).json()
    c = client.post("/api/v1/risk/forecast", json={"farm_id": 1, "mode": "conducive"}).json()
    assert n["weather"]["status"] == c["weather"]["status"] == "demo"
    assert c["risk"]["index"] > n["risk"]["index"]
    assert n["advisory"]["level"] == "info" and c["advisory"]["level"] == "watch"
    assert n["advisory"]["headline"] != c["advisory"]["headline"]


def test_live_weather_unavailable_without_key():
    r = client.get("/api/v1/weather", params={"farm_id": 1, "mode": "live"}).json()
    assert r["status"] == "unavailable" and "OPENWEATHER_API_KEY" in r["error"]
    f = client.post("/api/v1/risk/forecast", json={"farm_id": 1, "mode": "live"}).json()
    assert f["risk"]["status"] == "unavailable" and f["advisory"]["headline"]
    assert client.get("/api/v1/weather", params={"farm_id": 99, "mode": "live"}).status_code == 404


def test_live_weather_error_handling(monkeypatch):
    import httpx
    monkeypatch.setattr(config, "OWM_API_KEY", "x")

    class Boom:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def get(self, *a, **k): raise httpx.ConnectError("down")
    monkeypatch.setattr(httpx, "Client", lambda **k: Boom())
    r = weather.live_weather(1, 1)
    assert r["status"] == "unavailable" and "ConnectError" in r["error"]


def test_label_mapping():
    classes = json.loads(config.CLASSES_PATH.read_text())["classes"]
    assert len(classes) == 38 and classes[30] == "Tomato___Late_blight" and classes[37] == "Tomato___healthy"
    assert model.parse_label("Tomato___Late_blight") == ("Tomato", "Late blight")


def test_upload_validation():
    assert client.post("/api/v1/diagnose-image", files={"file": ("a.txt", b"hello", "text/plain")}).status_code == 422
    assert client.post("/api/v1/diagnose-image", files={"file": ("a.jpg", jpeg_bytes((20, 20)), "image/jpeg")}).status_code == 422
    assert client.post("/api/v1/diagnose-image", files={"file": ("a.jpg", b"", "image/jpeg")}).status_code == 400
    big = b"0" * (config.MAX_UPLOAD_BYTES + 10)
    assert client.post("/api/v1/diagnose-image", files={"file": ("a.jpg", big, "image/jpeg")}).status_code == 413
    gif = io.BytesIO(); Image.new("RGB", (100, 100)).save(gif, "GIF")
    assert client.post("/api/v1/diagnose-image", files={"file": ("a.gif", gif.getvalue(), "image/gif")}).status_code == 422


def test_inference_real_image_and_output_shape():
    r = client.post("/api/v1/diagnose-image", files={"file": ("leaf.jpg", jpeg_bytes(), "image/jpeg")}).json()
    assert r["status"] == "ok" and 0 <= r["score"] <= 1 and r["latency_ms"] > 0 and len(r["top3"]) == 3
    assert abs(sum(t["score"] for t in r["top3"])) <= 1.0 + 1e-6


@pytest.mark.skipif(not (SAMPLES / "late_blight").exists(), reason="PlantDoc samples not downloaded")
def test_known_late_blight_image():
    f = SAMPLES / "late_blight" / "110822-206-Tomato-blight.jpg"
    r = client.post("/api/v1/diagnose-image", files={"file": (f.name, f.read_bytes(), "image/jpeg")}).json()
    assert r["label"] == "Tomato___Late_blight" and r["is_tomato"]


def _img(label, score=0.9, tomato=True, low=False):
    crop, cond = model.parse_label(label)
    return {"status": "ok", "label": label, "crop": crop, "condition": cond, "score": score, "is_tomato": tomato, "low_confidence": low}


def test_advisory_combinations():
    hi, lo = assess("conducive"), assess("normal")
    lb, healthy = _img("Tomato___Late_blight"), _img("Tomato___healthy")
    assert advisory.build(hi, lb)["level"] == "alert"
    a = advisory.build(hi, healthy)
    assert a["level"] == "watch" and "not be visible" in " ".join(a["inspect"])
    a = advisory.build(lo, lb)
    assert a["level"] == "warning" and "Low weather risk does not cancel" in a["why"]
    assert advisory.build(lo, _img("Strawberry___Leaf_scorch", tomato=False))["level"] == "info"
    assert "outside" in advisory.build(lo, _img("Strawberry___Leaf_scorch", tomato=False))["what_is_happening"]
    unavailable_w = advisory.build({"status": "unavailable"}, lb)
    assert "unavailable" in unavailable_w["what_is_happening"] and unavailable_w["level"] == "warning"
    assert "unavailable" in advisory.build(hi, {"status": "unavailable"})["what_is_happening"]


def test_history_demo_labelled_and_session_record():
    h = client.get("/api/v1/risk/history").json()
    assert h["persistent"] is False
    client.post("/api/v1/risk/forecast", json={"farm_id": 1, "mode": "conducive", "record": True})
    h = client.get("/api/v1/risk/history", params={"farm_id": 1}).json()
    assert h["source"] == "session" and h["entries"][0]["synthetic"] is True


def test_database_layer_with_sqlite(tmp_path, monkeypatch):
    """MySQL is not installed here; this exercises the same SQLAlchemy models against SQLite."""
    from app import db
    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite:///{tmp_path/'t.db'}")
    db.init()
    assert db.enabled()
    a = assess("conducive")
    db.save_assessment(1, "conducive", a, weather.demo_series("conducive")[0], "warning", "x")
    db.save_image(1, {"status": "ok", "label": "Tomato___healthy", "score": 0.9, "latency_ms": 5.0}, "a.jpg")
    kinds = {e["type"] for e in db.history(1)}
    assert kinds == {"risk", "image"}
    db._engine = None


# ---- OpenWeatherMap integration (responses below are MOCKED fixtures shaped like the real API) ----
import time as _time
import httpx

_NOW = int(_time.time())
CUR = {"coord": {"lon": 73.79, "lat": 20.0}, "weather": [{"main": "Clouds", "description": "scattered clouds", "icon": "03d"}],
       "main": {"temp": 27.3, "feels_like": 29.1, "pressure": 1009, "humidity": 61}, "wind": {"speed": 3.2},
       "dt": _NOW, "sys": {"country": "IN"}, "timezone": 19800, "name": "Nashik"}
FC = {"city": {"name": "Nashik", "country": "IN", "timezone": 19800},
      "list": [{"dt": _NOW + 3600 * 3 * (i + 1), "main": {"temp": 25.0 - i * 0.1, "feels_like": 26.0, "pressure": 1008, "humidity": 70 + i % 20},
                "wind": {"speed": 2.0}, "weather": [{"main": "Rain", "description": "light rain", "icon": "10d"}],
                "pop": 0.4, **({"rain": {"3h": 0.8}} if i % 5 == 0 else {})} for i in range(40)]}


class FakeClient:
    calls = 0

    def __init__(self, cur=(200, CUR), fc=(200, FC), exc=None):
        self.cur, self.fc, self.exc = cur, fc, exc

    def __call__(self, **k):
        return self

    def __enter__(self): return self
    def __exit__(self, *a): pass

    def get(self, url, params=None):
        FakeClient.calls += 1
        assert params["units"] == "metric" and "appid" in params
        if self.exc:
            raise self.exc
        code, body = self.cur if url.endswith("/weather") else self.fc
        return httpx.Response(code, json=body, request=httpx.Request("GET", url))


def use(monkeypatch, **kw):
    monkeypatch.setattr(config, "OWM_API_KEY", "test-key")
    FakeClient.calls = 0
    monkeypatch.setattr(httpx, "Client", FakeClient(**kw))


def test_live_success_structure(monkeypatch):
    use(monkeypatch)
    r = client.get("/api/v1/weather", params={"farm_id": 1, "mode": "live"}).json()
    assert r["status"] == "live" and r["source"] == "OpenWeatherMap" and r["farm"]["id"] == 1
    assert r["location"]["name"] == "Nashik" and r["utc_offset_seconds"] == 19800 and r["fetched_at"] and r["observed_at"]
    c = r["current"]
    assert (c["temp_c"], c["feels_like_c"], c["rh"], c["pressure_hpa"], c["wind_ms"], c["icon"]) == (27.3, 29.1, 61, 1009, 3.2, "03d")
    assert len(r["series"]) == 41 and r["series"][1]["pop"] == 0.4 and r["series"][1]["rain_mm"] == 0.8
    assert "T" in r["series"][2]["time"] and r["series"][2]["time"].endswith("+05:30")


def test_live_feeds_risk_and_advisory(monkeypatch):
    use(monkeypatch)
    f = client.post("/api/v1/risk/forecast", json={"farm_id": 1, "mode": "live"}).json()
    assert f["weather"]["status"] == "live" and f["risk"]["status"] == "ok" and 0 <= f["risk"]["index"] <= 100


def test_cache_and_refresh(monkeypatch):
    use(monkeypatch)
    client.get("/api/v1/weather", params={"farm_id": 1, "mode": "live"})
    r2 = client.get("/api/v1/weather", params={"farm_id": 1, "mode": "live"}).json()
    assert FakeClient.calls == 2 and r2["cached"] is True  # one fetch = 2 HTTP calls
    r3 = client.get("/api/v1/weather", params={"farm_id": 1, "mode": "live", "refresh": True}).json()
    assert FakeClient.calls == 4 and r3["cached"] is False
    client.get("/api/v1/weather", params={"farm_id": 2, "mode": "live"})  # other location is not served from farm 1's cache
    assert FakeClient.calls == 6


def test_missing_fields_stay_none(monkeypatch):
    cur = {**CUR, "main": {"temp": 27.3}, "wind": None, "weather": []}
    use(monkeypatch, cur=(200, cur))
    c = client.get("/api/v1/weather", params={"farm_id": 1, "mode": "live"}).json()["current"]
    assert c["rh"] is None and c["pressure_hpa"] is None and c["wind_ms"] is None and c["icon"] is None


@pytest.mark.parametrize("code,needle", [(401, "2 hours"), (429, "rate limit"), (404, "location"), (500, "HTTP 500")])
def test_http_errors(monkeypatch, code, needle):
    use(monkeypatch, cur=(code, {"cod": code, "message": "x"}))
    r = client.get("/api/v1/weather", params={"farm_id": 1, "mode": "live"}).json()
    assert r["status"] == "unavailable" and needle in (r["error"] + (r.get("hint") or ""))
    assert "test-key" not in str(r)  # key never echoed


def test_timeout_and_malformed(monkeypatch):
    use(monkeypatch, exc=httpx.ReadTimeout("slow"))
    assert "timed out" in client.get("/api/v1/weather", params={"farm_id": 1, "mode": "live"}).json()["error"]
    use(monkeypatch, cur=(200, {"unexpected": True}))
    assert "unexpected response" in client.get("/api/v1/weather", params={"farm_id": 1, "mode": "live"}).json()["error"]
    use(monkeypatch, fc=(200, {"list": "nope"}))
    assert client.get("/api/v1/weather", params={"farm_id": 1, "mode": "live"}).json()["status"] == "unavailable"


def test_failed_live_not_cached_and_demo_still_labelled(monkeypatch):
    use(monkeypatch, cur=(401, {}))
    client.get("/api/v1/weather", params={"farm_id": 1, "mode": "live"})
    assert not weather._cache
    d = client.get("/api/v1/weather", params={"farm_id": 1, "mode": "conducive"}).json()
    assert d["status"] == "demo" and d["label"].startswith("Simulated") and d["source"] != "OpenWeatherMap"


def test_blank_env_values_fall_back_to_defaults(monkeypatch):
    """A copied .env.example leaves AGRISENTRY_MODEL_DIR= blank; that must mean 'use the default'."""
    import importlib
    monkeypatch.setenv("AGRISENTRY_MODEL_DIR", "")
    monkeypatch.setenv("CORS_ORIGINS", " ")
    c = importlib.reload(config)
    try:
        assert c.MODEL_DIR == c.ROOT / "models" and c.CLASSES_PATH.exists()
        assert c.CORS_ORIGINS == ["http://localhost:5173", "http://127.0.0.1:5173"]
    finally:
        monkeypatch.undo()
        importlib.reload(config)
