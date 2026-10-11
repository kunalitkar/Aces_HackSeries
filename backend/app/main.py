from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from . import advisory, config, db, model, risk, weather

app = FastAPI(title="AgriSentry API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

Mode = Literal["live", "normal", "conducive"]
_session_history: list[dict] = []  # volatile, used only when MySQL is not configured


@app.on_event("startup")
def _startup() -> None:
    db.init()
    model.load()


def _farm(farm_id: int) -> dict:
    for f in config.FARMS:
        if f["id"] == farm_id:
            return f
    raise HTTPException(404, f"Farm {farm_id} not found")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat(), "model": model.status(),
            "weather": {"live_configured": bool(config.OWM_API_KEY)}, "database": db.status()}


@app.get("/api/v1/farms")
def farms() -> list[dict]:
    return config.FARMS


def _weather_payload(w: dict) -> dict:
    out = {k: v for k, v in w.items() if k != "series"}
    out["series"] = w.get("series", [])
    return out


@app.get("/api/v1/weather")
def get_weather(farm_id: int, mode: Mode = "live", refresh: bool = False) -> dict:
    f = _farm(farm_id)
    return {"farm": f, **_weather_payload(weather.get_weather(mode, f["lat"], f["lon"], refresh))}


class ForecastRequest(BaseModel):
    farm_id: int
    mode: Mode = "live"
    image: dict[str, Any] | None = None  # the /diagnose-image response, if the user has one
    record: bool = False  # persist this assessment to history
    refresh: bool = False  # bypass the short-lived weather cache


@app.post("/api/v1/risk/forecast")
def forecast(req: ForecastRequest) -> dict:
    f = _farm(req.farm_id)
    w = weather.get_weather(req.mode, f["lat"], f["lon"], req.refresh)
    r = risk.assess(w["series"]) if w["status"] in ("live", "demo") else \
        {"status": "unavailable", "reason": w.get("error", "Weather unavailable")}
    adv = advisory.build(r, req.image)
    if req.record and r["status"] == "ok":
        db.save_assessment(f["id"], req.mode if req.mode != "live" else "live", r, w.get("current"), adv["level"], adv["headline"])
        _session_history.insert(0, {
            "id": f"s-{len(_session_history)}", "type": "risk", "farm_id": f["id"],
            "created_at": datetime.now(timezone.utc).isoformat(), "data_mode": req.mode,
            "title": f"Weather favourability {r['index']:.0f}/100 ({r['category']})", "detail": r["explanation"],
            "synthetic": req.mode != "live"})
        del _session_history[50:]
    return {"farm": f, "weather": _weather_payload(w), "risk": r, "advisory": adv}


@app.get("/api/v1/advisories")
def advisories(farm_id: int, mode: Mode = "live") -> dict:
    f = _farm(farm_id)
    w = weather.get_weather(mode, f["lat"], f["lon"])
    r = risk.assess(w["series"]) if w["status"] in ("live", "demo") else {"status": "unavailable"}
    return advisory.build(r, None)


@app.post("/api/v1/diagnose-image")
async def diagnose_image(file: UploadFile = File(...), farm_id: int | None = Form(None)) -> dict:
    data = await file.read(config.MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(400, "Uploaded file is empty.")
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Image exceeds the {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")
    try:
        res = model.classify(data)
    except model.ImageRejected as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, f"Inference error: {type(e).__name__}")
    if res["status"] == "ok":
        db.save_image(farm_id, res, file.filename)
        _session_history.insert(0, {
            "id": f"i-{len(_session_history)}", "type": "image", "farm_id": farm_id,
            "created_at": datetime.now(timezone.utc).isoformat(), "data_mode": "image", "synthetic": False,
            "title": f"Leaf image: {res['crop']} – {res['condition']}",
            "detail": f"Model softmax score {res['score']:.0%}; {res['latency_ms']:.0f} ms"})
    return res


def _synthetic_history() -> list[dict]:
    now = datetime.now(timezone.utc)
    rows = [(1, 18, "Weather favourability 62/100 (High)"), (2, 40, "Weather favourability 31/100 (Moderate)"),
            (3, 66, "Weather favourability 12/100 (Low)"), (4, 90, "Weather favourability 48/100 (Moderate)")]
    return [{"id": f"syn-{i}", "type": "risk", "farm_id": None, "created_at": (now - timedelta(hours=h)).isoformat(),
             "title": t, "detail": "Synthetic example entry for demonstration only.", "data_mode": "synthetic", "synthetic": True}
            for i, h, t in rows]


@app.get("/api/v1/risk/history")
def history(farm_id: int | None = None, limit: int = Query(30, le=100)) -> dict:
    if db.enabled():
        return {"source": "mysql", "persistent": True, "entries": db.history(farm_id, limit)}
    mine = [e for e in _session_history if farm_id is None or e["farm_id"] == farm_id][:limit]
    if mine:
        return {"source": "session", "persistent": False, "entries": mine}
    return {"source": "synthetic", "persistent": False, "entries": _synthetic_history()}
