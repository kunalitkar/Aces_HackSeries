import io
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import advisory, catalog, config, db, main, model, risk, weather  # noqa: E402

client = TestClient(main.app)
SAMPLES = config.ROOT / "data" / "plantdoc_samples"


@pytest.fixture(autouse=True)
def hermetic(monkeypatch, tmp_path):
    """Never use a real key from backend/.env, never reuse cached weather, fresh in-memory DB, temp uploads."""
    monkeypatch.setattr(config, "OWM_API_KEY", "")
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "uploads")
    weather._cache.clear()
    db.init("")


def jpeg_bytes(size=(300, 300), color=(60, 140, 60), fmt="JPEG"):
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, fmt)
    return b.getvalue()


def assess(mode):
    return risk.assess(weather.demo_series(mode))


def forecast(**kw):
    return client.post("/api/v1/risk/forecast", json={"farm_id": 1, **kw}).json()


# ---------------- health / model ----------------
def test_health():
    r = client.get("/api/health").json()
    assert r["status"] == "ok" and r["model"]["available"] is True and r["model"]["num_classes"] == 38
    assert r["database"]["persistent"] is False and r["database"]["backend"] == "sqlite"


def test_class_catalog_derived_from_classes_json():
    classes = json.loads(config.CLASSES_PATH.read_text())["classes"]
    m = client.get("/api/v1/model/classes").json()
    flat = [c["label"] for crop in m["crops"] for c in crop["classes"]]
    assert sorted(flat) == sorted(classes) and len(m["crops"]) == 14
    by = {c["crop"]: c for c in m["crops"]}
    assert by["Tomato"]["disease_classes"] == 9 and by["Orange"]["has_healthy_class"] is False
    assert by["Bell pepper"]["classes"][0]["label"].startswith("Pepper,_bell")
    assert m["weather_model"] == {"Tomato": "Late blight", "Potato": "Late blight"}
    for c in m["crops"]:  # class indices map back to the same label in classes.json
        for x in c["classes"]:
            assert classes[x["index"]] == x["label"]


def test_every_disease_class_has_catalogue_entry():
    classes = json.loads(config.CLASSES_PATH.read_text())["classes"]
    diseases = [c for c in classes if not c.endswith("___healthy")]
    assert len(diseases) == 26 and all(catalog.entry(c) for c in diseases)
    assert set(catalog.CATALOG) <= set(classes)


def test_model_card_sample_positive_control():
    f = config.ROOT / "data" / "model_card" / "sample_leaf.jpg"
    if not f.exists():
        pytest.skip("model card sample not present")
    assert model.classify(f.read_bytes())["label"] == "Apple___Apple_scab"


def test_label_parsing():
    assert model.parse_label("Tomato___Late_blight") == ("Tomato", "Late blight")
    assert model.parse_label("Pepper,_bell___Bacterial_spot") == ("Bell pepper", "Bacterial spot")
    assert model.parse_label("Corn_(maize)___Common_rust_") == ("Corn", "Common rust")
    assert model.parse_label("Cherry_(including_sour)___healthy") == ("Cherry", "healthy")


def test_crop_conditioning_math():
    model.load()
    classes = model._state["classes"]
    p = [0.0] * 38
    p[classes.index("Tomato___Late_blight")] = 0.3
    p[classes.index("Tomato___healthy")] = 0.1
    p[classes.index("Potato___Late_blight")] = 0.6
    import numpy as np
    r = model.interpret(np.array(p), "Tomato")
    assert r["label"] == "Tomato___Late_blight" and abs(r["score"] - 0.75) < 1e-9
    assert abs(r["crop_mass"] - 0.4) < 1e-9 and r["crop_mismatch"] and r["uncertain"]
    assert r["unrestricted_top3"][0]["label"] == "Potato___Late_blight"
    r2 = model.interpret(np.array(p), None)
    assert r2["label"] == "Potato___Late_blight" and r2["conditioned"] is False


def test_single_class_crop_not_renormalised():
    model.load()
    import numpy as np
    p = np.full(38, 0.5 / 37)
    p[model._state["classes"].index("Soybean___healthy")] = 0.5
    r = model.interpret(p, "Soybean")
    assert r["single_class_crop"] and abs(r["score"] - 0.5) < 1e-9 and r["uncertain"]


def test_upload_validation():
    post = lambda name, data, typ: client.post("/api/v1/diagnose-image", files={"file": (name, data, typ)})
    assert post("a.txt", b"hello", "text/plain").status_code == 422
    assert post("a.jpg", jpeg_bytes((20, 20)), "image/jpeg").status_code == 422
    assert post("a.jpg", b"", "image/jpeg").status_code == 400
    assert post("a.jpg", b"0" * (config.MAX_UPLOAD_BYTES + 10), "image/jpeg").status_code == 413
    gif = io.BytesIO(); Image.new("RGB", (100, 100)).save(gif, "GIF")
    assert post("a.gif", gif.getvalue(), "image/gif").status_code == 422
    r = client.post("/api/v1/diagnose-image", files={"file": ("a.jpg", jpeg_bytes(), "image/jpeg")}, data={"crop": "Banana"})
    assert r.status_code == 422 and "Unsupported crop" in r.json()["detail"]


def test_exif_rotation_applied():
    img = Image.new("RGB", (400, 200), (60, 140, 60))
    exif = img.getexif(); exif[0x0112] = 6  # rotate 90
    b = io.BytesIO(); img.save(b, "JPEG", exif=exif)
    model.load()
    assert model.preprocess(b.getvalue()).shape == (1, 3, 224, 224)


def test_inference_stores_image_reference_not_blob():
    r = client.post("/api/v1/diagnose-image", files={"file": ("leaf.jpg", jpeg_bytes(), "image/jpeg")}, data={"crop": "Tomato"}).json()
    assert r["status"] == "ok" and r["selected_crop"] == "Tomato" and r["crop"] == "Tomato" and len(r["top3"]) == 3
    assert (config.UPLOAD_DIR / r["image_ref"]).exists() and r["latency_ms"] > 0


@pytest.mark.skipif(not (SAMPLES / "late_blight").exists(), reason="PlantDoc samples not downloaded")
def test_known_late_blight_image():
    f = SAMPLES / "late_blight" / "110822-206-Tomato-blight.jpg"
    r = client.post("/api/v1/diagnose-image", files={"file": (f.name, f.read_bytes(), "image/jpeg")}, data={"crop": "Tomato"}).json()
    assert r["label"] == "Tomato___Late_blight" and not r["uncertain"]


# ---------------- risk engine ----------------
def test_scenarios_bounds_and_factor_sums():
    for mode in ("normal", "conducive"):
        a = assess(mode)
        assert a["status"] == "ok" and 0 <= a["index"] <= 100
        assert a["index"] == round(sum(f["points"] for f in a["factors"]), 1)
        assert all(0 <= f["points"] <= f["max_points"] for f in a["factors"])
        assert all(0 <= t["index"] <= 100 for t in a["trend"]) and len(a["trend"]) > 24
        assert len(a["intervals"]) == 60 and all(i["kind"] == "simulated" for i in a["intervals"])
    n, c = assess("normal"), assess("conducive")
    assert n["category"] == "Low" and c["category"] in ("High", "Very High") and c["index"] > n["index"] + 40
    assert n["favourable_hours_48h"] == 0 and c["favourable_hours_48h"] > 11


def test_missing_values_not_zero_filled():
    pts = weather.demo_series("conducive")
    for p in pts[:2]:
        p["rh"] = None
    a = risk.assess(pts)
    assert a["status"] == "ok" and a["factors"][2]["detail"].startswith("Mean RH 9")
    assert a["intervals"][0]["favourable"] is None
    for p in pts:
        p["rain_mm"] = None
    assert risk.assess(pts)["factors"][3]["available"] is False
    for p in pts:
        p["temp_c"] = None
    assert risk.assess(pts)["status"] == "unavailable"


def test_stale_observation_flagged():
    pts = weather.demo_series("conducive")
    for p in pts:
        p["kind"] = "forecast"
    pts[0]["kind"] = "observed"
    now = pts[0]["time"] + timedelta(hours=5)
    a = risk.assess(pts, now=now)
    assert a["stale"] is True and a["data_age_hours"] == 5 and "old" in a["explanation"]
    assert risk.assess(pts, now=pts[0]["time"] + timedelta(minutes=30))["stale"] is False


def test_rules_exposed_and_applicability():
    a = assess("normal")
    assert a["rules"]["components"][0]["max"] == 50 and "Experimental" in a["rules"]["status"]
    assert risk.applicable("tomato") == risk.applicable("Potato") == "Late blight"
    assert risk.applicable("Grape") is None


def test_forecast_scenarios_change_everything_consistently():
    n, c = forecast(mode="normal"), forecast(mode="conducive")
    assert n["weather"]["status"] == c["weather"]["status"] == "demo"
    assert c["risk"]["index"] > n["risk"]["index"]
    assert n["advisory"]["level"] == "info" and c["advisory"]["level"] == "watch"
    # advisory quotes the same assessment's numbers
    assert f"{c['risk']['index']:.0f}/100" in c["advisory"]["what_is_happening"]


def test_other_crops_get_no_weather_prediction():
    for crop in ("Grape", "Apple", "Corn"):
        f = forecast(mode="conducive", crop=crop)
        assert f["risk"]["status"] == "not_applicable" and f["crop"] == crop
        assert f["new_alerts"] == [] and "no validated weather-risk model" in f["advisory"]["what_is_happening"]
    assert forecast(mode="conducive", crop="Potato")["risk"]["status"] == "ok"
    assert client.post("/api/v1/risk/forecast", json={"farm_id": 1, "crop": "Banana"}).status_code == 422


def test_image_for_other_crop_is_ignored():
    img = {"status": "ok", "selected_crop": "Grape", "label": "Grape___Black_rot"}
    f = forecast(mode="normal", crop="Tomato", image=img)
    assert f["image_ignored"] is True and "No leaf image" in f["advisory"]["what_is_happening"]


def test_live_weather_unavailable_without_key():
    r = client.get("/api/v1/weather", params={"farm_id": 1, "mode": "live"}).json()
    assert r["status"] == "unavailable" and "OPENWEATHER_API_KEY" in r["error"]
    f = forecast(mode="live")
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


# ---------------- location ----------------
def test_adhoc_location_is_rounded_and_not_stored():
    f = forecast(farm_id=None, location={"lat": 18.520430, "lon": 73.856743}, mode="conducive", record=True)
    assert f["place"]["kind"] == "location" and (f["place"]["lat"], f["place"]["lon"]) == (18.52, 73.86)
    assert f["place"]["farm_id"] is None and f["crop"] == "Tomato" and "current location" in f["place"]["label"]
    assert len(db.list_farms()) == 4  # nothing saved as a farm without consent
    saved = db.list_assessments()[0]
    assert "18.52" not in json.dumps(saved) and "73.8" not in json.dumps(saved)
    assert all("18.52" not in json.dumps(a) for a in db.list_alerts())


def test_location_validation():
    assert client.post("/api/v1/risk/forecast", json={"location": {"lat": 91, "lon": 0}}).status_code == 422
    assert client.post("/api/v1/risk/forecast", json={}).status_code == 422


def test_geocode_without_key_reports_error():
    r = client.get("/api/v1/geocode", params={"q": "Nashik"}).json()
    assert r["status"] == "error" and r["results"] == []


# ---------------- farms ----------------
def test_farm_crud():
    f = client.post("/api/v1/farms", json={"name": "My plot", "location": "Pune", "lat": 18.5204, "lon": 73.8567, "crop": "potato"})
    assert f.status_code == 201 and f.json()["crop"] == "Potato"
    fid = f.json()["id"]
    assert any(x["id"] == fid for x in client.get("/api/v1/farms").json())
    assert forecast(farm_id=fid, mode="normal")["farm"]["name"] == "My plot"
    assert client.delete("/api/v1/farms/1").status_code == 400  # seeds protected
    assert client.delete(f"/api/v1/farms/{fid}").status_code == 200
    assert client.delete(f"/api/v1/farms/{fid}").status_code == 404
    assert client.post("/api/v1/farms", json={"name": "x", "lat": 100, "lon": 0}).status_code == 422
    assert client.post("/api/v1/farms", json={"name": "x", "lat": 1, "lon": 1, "crop": "Banana"}).status_code == 422


# ---------------- advisory ----------------
def _img(label, score=0.9, uncertain=False, **kw):
    crop, cond = model.parse_label(label)
    return {"status": "ok", "label": label, "crop": crop, "condition": cond, "score": score, "healthy": cond == "healthy",
            "low_confidence": score < 0.5, "uncertain": uncertain or score < 0.5, "crop_mismatch": False,
            "single_class_crop": False, "selected_crop": crop, "unrestricted_top3": [], **kw}


def test_advisory_combinations():
    hi, lo = assess("conducive"), assess("normal")
    lb, healthy = _img("Tomato___Late_blight"), _img("Tomato___healthy")
    a = advisory.build(hi, lb, "Tomato")
    assert a["level"] == "alert" and any("Look for" in i for i in a["inspect"])
    a = advisory.build(hi, healthy, "Tomato")
    assert a["level"] == "watch" and "not be visible" in " ".join(a["inspect"])
    a = advisory.build(lo, lb, "Tomato")
    assert a["level"] == "warning" and "Low weather risk does not cancel" in a["what_is_happening"]
    a = advisory.build(lo, _img("Tomato___Septoria_leaf_spot"), "Tomato")
    assert a["level"] == "warning" and "late blight only" in a["what_is_happening"]
    assert a["actions"] == catalog.entry("Tomato___Septoria_leaf_spot")["prevent"]
    a = advisory.build(lo, _img("Tomato___Late_blight", score=0.3), "Tomato")
    assert a["level"] == "watch" and "unsure" in a["what_is_happening"]
    mm = _img("Tomato___healthy", uncertain=True, crop_mismatch=True, crop_mass=0.2,
              unrestricted_top3=[{"crop": "Grape", "condition": "Black rot"}])
    assert "does not look like Tomato" in advisory.build(lo, mm, "Tomato")["what_is_happening"]
    soy = _img("Soybean___healthy", score=0.4, single_class_crop=True)
    assert "only one class" in advisory.build(risk.not_applicable("Soybean"), soy, "Soybean")["what_is_happening"]
    assert "unavailable" in advisory.build({"status": "unavailable"}, lb, "Tomato")["what_is_happening"]
    assert "unavailable" in advisory.build(hi, {"status": "unavailable"}, "Tomato")["what_is_happening"]


def test_advisory_never_claims_severity_or_doses():
    a = advisory.build(assess("conducive"), _img("Tomato___Late_blight"), "Tomato")
    assert a["severity"]["available"] is False
    text = json.dumps(a).lower()
    for banned in ("ml/l", "g/l", "kg/ha", "mancozeb", "metalaxyl", "spray every"):
        assert banned not in text


# ---------------- history / alerts / persistence ----------------
def test_history_is_genuine_only():
    h = client.get("/api/v1/risk/history").json()
    assert h["entries"] == [] and h["persistent"] is False
    img = client.post("/api/v1/diagnose-image", files={"file": ("leaf.jpg", jpeg_bytes(), "image/jpeg")}, data={"crop": "Tomato"}).json()
    forecast(mode="conducive", image=img, record=True)
    e = client.get("/api/v1/risk/history", params={"farm_id": 1}).json()["entries"][0]
    assert e["crop"] == "Tomato" and e["simulated"] is True and e["predicted_label"] == img["label"]
    assert e["confidence"] == img["score"] and e["risk_category"] in ("High", "Very High") and e["model_version"]
    assert e["image_ref"] == img["image_ref"] and e["recommendation"]


def test_alert_threshold_suppression_escalation_and_ack():
    assert forecast(mode="normal")["new_alerts"] == []  # Low -> no alert
    first = forecast(mode="conducive")["new_alerts"]
    assert len(first) == 1 and first[0]["simulated"] is True and first[0]["kind"] == "weather"
    assert forecast(mode="conducive")["new_alerts"] == []  # unchanged -> suppressed
    assert forecast(farm_id=2, mode="conducive")["new_alerts"]  # other location alerts independently
    # escalation High -> Very High alerts again even within 24 h
    key, label = "farm:3", "x"
    r = {"status": "ok", "category": "High", "index": 60, "explanation": "e", "peak_48h": None}
    assert db.evaluate_weather_alert(location_key=key, location_label=label, farm_id=3, risk=r, simulated=False)
    assert db.evaluate_weather_alert(location_key=key, location_label=label, farm_id=3, risk=r, simulated=False) is None
    assert db.evaluate_weather_alert(location_key=key, location_label=label, farm_id=3, risk={**r, "category": "Very High"}, simulated=False)
    # live and simulated are tracked separately
    assert db.evaluate_weather_alert(location_key=key, location_label=label, farm_id=3, risk=r, simulated=True)
    al = client.get("/api/v1/alerts").json()
    n = al["unacknowledged"]
    aid = al["alerts"][0]["id"]
    ack = client.post(f"/api/v1/alerts/{aid}/acknowledge").json()
    assert ack["acknowledged"] and ack["acknowledged_at"]
    assert client.get("/api/v1/alerts").json()["unacknowledged"] == n - 1
    assert all(a["id"] != aid for a in client.get("/api/v1/alerts", params={"include_acknowledged": False}).json()["alerts"])
    assert client.post("/api/v1/alerts/9999/acknowledge").status_code == 404


def test_forecast_peak_triggers_early_warning_alert():
    r = {"status": "ok", "category": "Moderate", "index": 40, "explanation": "e",
         "peak_48h": {"category": "High", "index": 62, "time": datetime.now(timezone.utc)}}
    a = db.evaluate_weather_alert(location_key="k", location_label="L", farm_id=None, risk=r, simulated=False)
    assert a and "forecast to reach High within 48 h" in a["message"]


def test_file_database_persists_across_restart(tmp_path):
    """Same SQLAlchemy code path as MySQL, against a SQLite file (MySQL credentials not available here)."""
    url = f"sqlite:///{tmp_path / 'p.db'}"
    db.init(url)
    assert db.status()["persistent"] is True
    fid = db.create_farm("Saved", "Pune", 18.52, 73.86, "Tomato")["id"]
    forecast(farm_id=fid, mode="conducive", record=True)
    db.init(url)  # simulate restart
    assert any(f["id"] == fid for f in db.list_farms()) and db.list_assessments(fid) and db.list_alerts()


def test_additive_migration_adds_missing_columns(tmp_path):
    import sqlalchemy as sa
    url = f"sqlite:///{tmp_path / 'old.db'}"
    eng = sa.create_engine(url)
    with eng.begin() as c:  # MVP-era alerts table without the new columns, containing a row
        c.execute(sa.text("CREATE TABLE alerts (id INTEGER PRIMARY KEY, farm_id INTEGER, created_at DATETIME, level VARCHAR(20), message TEXT)"))
        c.execute(sa.text("INSERT INTO alerts (farm_id, created_at, level, message) VALUES (1, '2026-01-01', 'warning', 'old')"))
    eng.dispose()
    db.init(url)
    assert db.status()["persistent"] is True and db.status()["error"] is None
    al = db.list_alerts()
    assert al[0]["message"] == "old" and al[0]["acknowledged"] is False  # data kept, new columns added


def test_bad_database_url_falls_back_to_labelled_memory():
    db.init("mysql+pymysql://nobody:wrong@127.0.0.1:1/agrisentry")
    st = db.status()
    assert st["persistent"] is False and st["connected"] and "Could not use DATABASE_URL" in st["error"]


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
