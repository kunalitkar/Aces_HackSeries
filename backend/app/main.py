from __future__ import annotations
import hashlib
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Literal
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from . import advisory, chat, config, db, model, risk, weather


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init()
    model.load()
    yield


app = FastAPI(title="AgriSentry API", version="0.3.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

Mode = Literal["live", "normal", "conducive"]
EXT = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


class Coordinates(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    label: str | None = Field(default=None, max_length=120)


def _crops() -> list[str]:
    return [c["crop"] for c in model.class_catalog()] or ["Tomato"]


def _check_crop(crop: str | None) -> str | None:
    if crop is None:
        return None
    for c in _crops():
        if c.lower() == crop.strip().lower():
            return c
    raise HTTPException(422, f"Unsupported crop '{crop}'. Supported: {', '.join(_crops())}.")


def _resolve(farm_id: int | None, location: Coordinates | None) -> dict:
    """Selected place: a saved farm, or an ad-hoc location (current position / search result)."""
    if location is not None:
        lat, lon = round(location.lat, 2), round(location.lon, 2)  # ~1 km: approximate, never stored
        key = "loc:" + hashlib.sha256(f"{lat:.2f},{lon:.2f}".encode()).hexdigest()[:16]
        return {"kind": "location", "farm_id": None, "lat": lat, "lon": lon, "label": location.label, "key": key, "crop": None}
    if farm_id is None:
        raise HTTPException(422, "Provide farm_id or location.")
    f = db.get_farm(farm_id)
    if not f:
        raise HTTPException(404, f"Farm {farm_id} not found")
    return {"kind": "farm", "farm_id": f["id"], "lat": f["lat"], "lon": f["lon"], "label": f"{f['name']}, {f['location']}",
            "key": f"farm:{f['id']}", "crop": f["crop"], "farm": f}


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat(), "model": model.status(),
            "weather": {"live_configured": bool(config.OWM_API_KEY)}, "chat": chat.status(), "database": db.status()}


# ---------- farms & locations ----------
class FarmIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    location: str = Field(default="", max_length=160)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    crop: str = "Tomato"


@app.get("/api/v1/farms")
def farms() -> list[dict]:
    return db.list_farms()


@app.post("/api/v1/farms", status_code=201)
def create_farm(body: FarmIn) -> dict:
    """Saving is an explicit user choice; only then are coordinates stored."""
    return db.create_farm(body.name.strip(), body.location.strip() or f"{body.lat:.3f}, {body.lon:.3f}",
                          round(body.lat, 4), round(body.lon, 4), _check_crop(body.crop))


@app.delete("/api/v1/farms/{farm_id}")
def delete_farm(farm_id: int) -> dict:
    f = db.get_farm(farm_id)
    if not f:
        raise HTTPException(404, f"Farm {farm_id} not found")
    if f["is_seed"]:
        raise HTTPException(400, "Built-in demo farms cannot be deleted.")
    db.delete_farm(farm_id)
    return {"deleted": farm_id}


@app.get("/api/v1/geocode")
def geocode(q: str = Query(min_length=1, max_length=100)) -> dict:
    return weather.geocode(q)


@app.get("/api/v1/model/classes")
def model_classes() -> dict:
    st = model.status()
    return {"available": st["available"], "version": st["version"], "error": st["error"], "crops": model.class_catalog(),
            "weather_model": {c.title(): d for c, d in risk.APPLICABLE.items()}}


# ---------- weather / risk ----------
def _weather_payload(w: dict) -> dict:
    return {**{k: v for k, v in w.items() if k != "series"}, "series": w.get("series", [])}


@app.get("/api/v1/weather")
def get_weather(farm_id: int | None = None, mode: Mode = "live", refresh: bool = False) -> dict:
    place = _resolve(farm_id, None)
    return {"farm": place.get("farm"), **_weather_payload(weather.get_weather(mode, place["lat"], place["lon"], refresh))}


class ForecastRequest(BaseModel):
    farm_id: int | None = None
    location: Coordinates | None = None   # ad-hoc location (consent-based current position or search result)
    crop: str | None = None               # defaults to the farm's crop
    mode: Mode = "live"
    image: dict[str, Any] | None = None   # the /diagnose-image response, if the user has one
    record: bool = False                  # save as an assessment (history)
    refresh: bool = False                 # bypass the short-lived weather cache


def _assess(place: dict, crop: str, mode: str, refresh: bool) -> tuple[dict, dict]:
    w = weather.get_weather(mode, place["lat"], place["lon"], refresh)
    if not risk.applicable(crop):
        r = risk.not_applicable(crop)
    elif w["status"] in ("live", "demo"):
        r = risk.assess(w["series"], now=datetime.now(timezone.utc) if w["status"] == "live" else None)
    else:
        r = {"status": "unavailable", "reason": w.get("error", "Weather unavailable")}
    return w, r


@app.post("/api/v1/risk/forecast")
def forecast(req: ForecastRequest) -> dict:
    place = _resolve(req.farm_id, req.location)
    crop = _check_crop(req.crop) or place["crop"] or "Tomato"
    w, r = _assess(place, crop, req.mode, req.refresh)
    image = req.image if req.image and (req.image.get("selected_crop") in (None, crop)) else None
    adv = advisory.build(r, image, crop)
    label = place["label"] or (w.get("location") or {}).get("name") or "Current location"
    if place["kind"] == "location" and not place["label"]:
        label = f"Near {label} (current location)"
    alerts = []
    a = db.evaluate_weather_alert(location_key=place["key"], location_label=label, farm_id=place["farm_id"], risk=r,
                                  simulated=req.mode != "live")
    if a:
        alerts.append(a)
    saved = None
    if req.record:
        saved = db.save_assessment(farm_id=place["farm_id"], location_label=label, crop=crop, mode=req.mode,
                                   weather=w, risk=r, image=image, advisory=adv)
        ia = db.image_alert(farm_id=place["farm_id"], location_label=label, advisory=adv, image=image or {})
        if ia:
            alerts.append(ia)
    return {"farm": place.get("farm"), "place": {"kind": place["kind"], "label": label, "farm_id": place["farm_id"],
            "lat": place["lat"], "lon": place["lon"]}, "crop": crop, "weather": _weather_payload(w), "risk": r,
            "advisory": adv, "new_alerts": alerts, "saved": saved, "image_ignored": bool(req.image) and image is None}


@app.get("/api/v1/advisories")
def advisories(farm_id: int, mode: Mode = "live", crop: str | None = None) -> dict:
    place = _resolve(farm_id, None)
    crop = _check_crop(crop) or place["crop"]
    _, r = _assess(place, crop, mode, False)
    return advisory.build(r, None, crop)


# ---------- image ----------
@app.post("/api/v1/diagnose-image")
async def diagnose_image(file: UploadFile = File(...), farm_id: int | None = Form(None), crop: str | None = Form(None),
                         region: str | None = Form(None), force: bool = Form(False)) -> dict:
    """region: optional user-selected leaf area "x,y,w,h" as fractions of the original image.
    force: classify even if the photo fails the quality check (result is then marked uncertain)."""
    crop = _check_crop(crop) if crop else None
    box = None
    if region:
        try:
            box = tuple(float(v) for v in region.split(","))
            assert len(box) == 4
        except (ValueError, AssertionError):
            raise HTTPException(422, "region must be 'x,y,w,h' fractions between 0 and 1.")
    data = await file.read(config.MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(400, "Uploaded file is empty.")
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Image exceeds the {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")
    try:
        res = model.classify(data, crop, box, force)
    except model.ImageRejected as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, f"Inference error: {type(e).__name__}")
    if res["status"] == "ok":
        from PIL import Image
        import io
        fmt = Image.open(io.BytesIO(data)).format
        config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        # The ORIGINAL photo is kept (named by content hash, so re-analysing another leaf of it stores no copy).
        ref = f"{hashlib.sha256(data).hexdigest()[:32]}{EXT.get(fmt, '.img')}"
        if not (config.UPLOAD_DIR / ref).exists():
            (config.UPLOAD_DIR / ref).write_bytes(data)
        res["image_ref"] = ref
        db.save_image(farm_id, res, file.filename, ref)
    return res


# ---------- history & alerts ----------
@app.get("/api/v1/risk/history")
def history(farm_id: int | None = None, limit: int = Query(50, le=200)) -> dict:
    st = db.status()
    return {"persistent": st["persistent"], "backend": st["backend"], "entries": db.list_assessments(farm_id, limit)}


@app.get("/api/v1/alerts")
def alerts(include_acknowledged: bool = True) -> dict:
    items = db.list_alerts(include_acknowledged)
    return {"persistent": db.status()["persistent"], "unacknowledged": sum(not a["acknowledged"] for a in items), "alerts": items}


@app.post("/api/v1/alerts/{alert_id}/acknowledge")
def acknowledge(alert_id: int) -> dict:
    a = db.acknowledge_alert(alert_id)
    if not a:
        raise HTTPException(404, f"Alert {alert_id} not found")
    return a


# ---------- Ask AgriSentry (chat grounded in the current assessment) ----------
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=chat.MAX_MESSAGE_CHARS * 2)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    farm_id: int | None = None
    location: Coordinates | None = None
    crop: str | None = None
    mode: Mode = "live"
    image: dict[str, Any] | None = None


@app.post("/api/v1/chat")
def ask_agrisentry(req: ChatRequest) -> dict:
    """The assessment is recomputed here from the server's own engines; nothing numeric is trusted from the client."""
    if not config.GROQ_API_KEY:  # fail fast: do not spend weather/API calls when chat cannot answer
        return chat.ask([m.model_dump() for m in req.messages], "")
    place = _resolve(req.farm_id, req.location)
    crop = _check_crop(req.crop) or place["crop"] or "Tomato"
    w, r = _assess(place, crop, req.mode, False)
    image = req.image if req.image and (req.image.get("selected_crop") in (None, crop)) else None
    adv = advisory.build(r, image, crop)
    label = place["label"] if place["kind"] == "farm" else "the farmer's chosen location"  # never send coordinates
    ctx = chat.build_context(label, crop, req.mode, w, r, adv, image)
    res = chat.ask([m.model_dump() for m in req.messages], ctx)
    res["grounding"] = {"place": label, "crop": crop, "weather_status": w["status"], "risk_level": r.get("category"),
                        "image": (image or {}).get("label")}
    return res
