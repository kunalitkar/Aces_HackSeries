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
os.environ.pop("OPENWEATHER_API_KEY", None)
from app import advisory, config, main, model, risk, weather  # noqa: E402

client = TestClient(main.app)
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
