"""Photo-quality gate, user-selected leaf region, and farmer-facing weather-risk fields."""
from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image, ImageEnhance, ImageFilter

from test_backend import SAMPLES, advisory, assess, client, config, db, forecast, jpeg_bytes, risk, textured  # noqa: F401
from test_backend import hermetic  # noqa: F401  (autouse fixture)
from app import quality

PHOTOS = {  # real PlantDoc test photos picked by eye for these situations
    "single_closeup": SAMPLES / "late_blight" / "18c.jpg",
    "multi_leaf": SAMPLES / "late_blight" / "late_blight_tomato_leaf_spore1x1200.jpg",
    "multi_leaf_2": SAMPLES / "early_blight" / "dscn3175.jpg",
    "whole_plant": SAMPLES / "early_blight" / "bugs-and-blight-061.jpg",
    "whole_plant_2": SAMPLES / "healthy" / "Tomato59.JPG.jpg",
    "small_150px": SAMPLES / "early_blight" / "early_blight1-150x150.jpg",
}
need_photos = pytest.mark.skipif(not all(p.exists() for p in PHOTOS.values()), reason="PlantDoc samples not downloaded")


def diagnose(data, **form):
    return client.post("/api/v1/diagnose-image", files={"file": ("x.jpg", data, "image/jpeg")}, data={"crop": "Tomato", **form})


def photo(key, transform=None):
    img = Image.open(PHOTOS[key]).convert("RGB")
    return jpeg_bytes(img=transform(img) if transform else img)


# ---------------- quality gate ----------------
@need_photos
def test_real_photos_pass_quality_gate_including_multi_leaf_and_whole_plant():
    for key in ("single_closeup", "multi_leaf", "multi_leaf_2", "whole_plant", "whole_plant_2"):
        r = diagnose(photo(key)).json()
        assert r["status"] == "ok", key  # several leaves / whole plant are never rejected for that reason
        assert r["quality"]["status"] in ("ok", "warn") and r["region"] is None
        assert r["label"] and 0 <= r["score"] <= 1 and len(r["top3"]) == 3  # existing response contract


@need_photos
def test_blurry_photo_blocked_with_actionable_message():
    r = diagnose(photo("single_closeup", lambda i: i.resize((512, 512)).filter(ImageFilter.GaussianBlur(4)))).json()
    assert r["status"] == "quality_failed" and "label" not in r
    assert any(c["key"] == "sharpness" and c["status"] == "fail" and "blurry" in c["message"] for c in r["quality"]["checks"])


@need_photos
def test_dark_photo_blocked_and_analyse_anyway_marks_uncertain():
    dark = photo("single_closeup", lambda i: ImageEnhance.Brightness(i).enhance(0.12))
    r = diagnose(dark).json()
    assert r["status"] == "quality_failed" and any("too dark" in c["message"] for c in r["quality"]["checks"])
    forced = diagnose(dark, force="true").json()
    assert forced["status"] == "ok" and forced["quality_override"] and forced["uncertain"]
    a = advisory.build(assess("normal"), forced, "Tomato")
    assert a["headline"] == "Photo quality too low – retake photo" and "not reliable" in a["what_is_happening"]


@need_photos
def test_low_resolution_real_photo_warns_but_is_analysed():
    r = diagnose(photo("small_150px")).json()
    assert r["status"] == "ok" and r["quality_limited"] and not r["quality_override"]
    assert any(c["key"] == "resolution" and c["status"] == "warn" for c in r["quality"]["checks"])
    assert "Photo quality is limited" in advisory.build(assess("normal"), r, "Tomato")["what_is_happening"]


def test_quality_thresholds_on_synthetic_cases():
    img = textured((400, 400))
    assert quality.assess(img)["status"] == "ok"
    assert quality.assess(img.filter(ImageFilter.GaussianBlur(4)))["status"] == "fail"
    assert quality.assess(ImageEnhance.Brightness(img).enhance(0.25))["checks"][0]["key"] == "brightness"
    assert quality.assess(Image.new("RGB", (400, 400), (255, 255, 255)))["status"] == "fail"  # flat white: no detail
    assert any(c["key"] == "resolution" for c in quality.assess(textured((150, 150)))["checks"])
    t = {**quality.THRESHOLDS, "sharpness_fail": 0, "sharpness_warn": 0}  # thresholds are configurable
    assert quality.assess(img.filter(ImageFilter.GaussianBlur(4)), t)["status"] == "ok"


def test_quality_failed_image_not_used_by_advisory_as_prediction():
    qf = {"status": "quality_failed", "selected_crop": "Tomato",
          "quality": {"status": "fail", "checks": [{"key": "sharpness", "status": "fail", "message": "The photo is blurry."}]}}
    a = advisory.build(assess("conducive"), qf, "Tomato")
    assert "not analysed because of its quality" in a["what_is_happening"] and a["level"] == "watch"
    assert a["inspect"][0].startswith("Retake")


# ---------------- user-selected leaf region ----------------
@need_photos
def test_region_crop_analyses_selected_leaf_and_keeps_original():
    full = photo("multi_leaf")
    whole = diagnose(full).json()
    part = diagnose(full, region="0.1,0.1,0.5,0.6").json()
    assert part["status"] == "ok" and part["region"] == {"x": 0.1, "y": 0.1, "w": 0.5, "h": 0.6}
    assert part["image_ref"] == whole["image_ref"]  # same original stored once
    assert (config.UPLOAD_DIR / part["image_ref"]).read_bytes() == full


def test_region_validation():
    big = jpeg_bytes((400, 400))
    assert diagnose(big, region="0.1,0.1").status_code == 422
    assert diagnose(big, region="a,b,c,d").status_code == 422
    assert diagnose(big, region="0.5,0.5,0.6,0.6").json()["status"] == "ok"  # clipped to the image
    r = diagnose(big, region="0,0,0.05,0.05")
    assert r.status_code == 422 and "too small" in r.json()["detail"]
    assert diagnose(big, region="1.2,0,0.5,0.5").status_code == 422


def test_image_prediction_row_records_region_and_quality():
    diagnose(jpeg_bytes((400, 400)), region="0,0,0.5,0.5")
    with db.session() as s:
        row = s.scalars(db.select(db.ImagePrediction).order_by(db.ImagePrediction.id.desc())).first()
    assert row.region == "0.0000,0.0000,0.5000,0.5000" and row.quality_status in ("ok", "warn")


# ---------------- farmer-facing risk fields ----------------
def _series(temp, rh, rain=0.0, hours=48):
    t0 = datetime(2026, 10, 11, 0, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    return [{"time": t0 + timedelta(hours=h), "temp_c": temp, "rh": rh, "rain_mm": rain, "kind": "forecast"} for h in range(hours)]


def test_all_four_categories():
    got = {a: (risk.assess(_series(*a))["index"], risk.assess(_series(*a))["category"]) for a in [(30, 50), (20, 80), (25, 90), (20, 92, 0.5)]}
    assert got == {(30, 50): (0.0, "Low"), (20, 80): (28.0, "Moderate"), (25, 90): (74.0, "High"), (20, 92, 0.5): (97.6, "Very High")}
    for c in ("Low", "Moderate", "High", "Very High"):
        assert risk.LEVEL_TEXT[c] and risk.DAY_ACTION[c]


def test_factor_readings_match_scored_values():
    a = risk.assess(_series(20, 92, 0.5))
    f = {x["key"]: x for x in a["factors"]}
    assert f["temperature"]["value"] == 20.0 and "Mostly within 15–22" in f["temperature"]["interpretation"]
    assert f["humidity"]["value"] == 92 and "Very humid" in f["humidity"]["interpretation"]
    assert f["duration"]["value"] == 12.0 and "fully favourable" in f["duration"]["interpretation"]
    assert f["rain"]["value"] == 6.0 and "plenty" in f["rain"]["interpretation"]
    dry = {x["key"]: x for x in risk.assess(_series(30, 50))["factors"]}
    assert dry["temperature"]["points"] == 0 and "Always outside" in dry["temperature"]["interpretation"]
    assert dry["humidity"]["points"] == 0 and "no humidity risk" in dry["humidity"]["interpretation"]
    assert dry["duration"]["points"] == 0 and dry["duration"]["interpretation"].startswith("No hours")
    assert all(x["why"] and x["name"] for x in a["factors"])


def test_missing_rain_reads_data_unavailable():
    rain = risk.assess([{**p, "rain_mm": None} for p in _series(20, 92)])["factors"][3]
    assert rain["value"] is None and rain["interpretation"] == "Data unavailable" and rain["available"] is False


def test_period_basis_current_vs_forecast_vs_simulated():
    pts = _series(20, 92)
    assert risk.assess(pts)["period"]["basis"] == "forecast"
    pts[0]["kind"] = "observed"
    assert risk.assess(pts)["period"]["basis"] == "current observation + forecast"
    assert assess("normal")["period"]["basis"] == "simulated"


def test_daily_risk_varies_by_day_and_skips_unscored_days():
    # dry for 2 days, then a wet day. A window starting late on day 2 reaches into day 3, so day 2 shows the
    # coming risk (by design: each day = highest 12 h window starting that day); day 1 stays Low.
    wet = [{**p, "time": p["time"] + timedelta(hours=48)} for p in _series(20, 93, 0.5, hours=24)]
    days = risk.assess(_series(30, 50, hours=48) + wet)["daily"]
    assert [d["date"] for d in days] == ["2026-10-11", "2026-10-12", "2026-10-13"]
    assert days[0]["category"] == "Low" and days[0]["main_factor"] is None
    assert days[2]["category"] in ("High", "Very High")  # not one value repeated across days
    assert days[2]["main_factor"] == "Cool, wet hours in a row" and days[2]["action"]
    assert days[0]["weather"]["temp_max"] == 30 and days[2]["weather"]["rain_mm"] == 12.0
    assert days[2]["partial"] is True and days[0]["partial"] is False  # last day: windows stop where data runs out
    assert len(risk.assess(_series(20, 92, hours=10))["daily"]) == 1


def test_daily_missing_values_stay_none():
    pts = [{**p, "rh": None if i % 2 else p["rh"]} for i, p in enumerate(_series(20, 92))]
    d = risk.assess(pts)["daily"][0]
    assert d["weather"]["rh_mean"] == 92 and d["weather"]["description"] is None


def test_forecast_response_is_backward_compatible_and_extended():
    f = forecast(mode="conducive")
    r = f["risk"]
    for k in ("index", "category", "factors", "trend", "explanation", "rules", "intervals"):  # existing fields kept
        assert k in r
    assert r["level_text"] and r["period"]["basis"] == "simulated" and r["daily"]
    assert f["advisory"]["inspect"] and f["advisory"]["actions"]
    assert forecast(mode="conducive", crop="Grape")["risk"]["status"] == "not_applicable"
