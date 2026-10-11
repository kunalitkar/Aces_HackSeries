from __future__ import annotations
import math
from datetime import datetime, timedelta, timezone
import httpx
from . import config

IST = timezone(timedelta(hours=5, minutes=30))
SCENARIOS = {
    "normal": "Simulated: normal, warm and dry conditions",
    "conducive": "Simulated: disease-conducive (cool, humid, showery)",
}


def demo_series(scenario: str, hours: int = 60, now: datetime | None = None) -> list[dict]:
    start = (now or datetime.now(IST)).replace(minute=0, second=0, microsecond=0)
    out = []
    for h in range(hours):
        t = start + timedelta(hours=h)
        diurnal = math.cos((t.hour - 15) / 24 * 2 * math.pi)  # +1 at 15:00, -1 at 03:00
        if scenario == "normal":
            temp, rh, rain = 28.5 + 4.0 * diurnal, 55 - 14 * diurnal, 0.0
        else:
            temp = 19.0 + 2.5 * diurnal
            rh = 92 - 5 * diurnal + 1.5 * math.sin(h / 3)
            rain = 1.2 if (6 <= h < 10 or 26 <= h < 32) else 0.0
        out.append({"time": t, "temp_c": round(temp, 1), "rh": round(min(rh, 99)), "rain_mm": rain})
    return out


def _unavailable(error: str) -> dict:
    return {"status": "unavailable", "label": "Live weather unavailable", "error": error}


def live_weather(lat: float, lon: float) -> dict:
    if not config.OWM_API_KEY:
        return _unavailable("OPENWEATHER_API_KEY is not configured on the server.")
    try:
        p = {"lat": lat, "lon": lon, "units": "metric", "appid": config.OWM_API_KEY}
        with httpx.Client(timeout=8) as c:
            cur = c.get("https://api.openweathermap.org/data/2.5/weather", params=p)
            fc = c.get("https://api.openweathermap.org/data/2.5/forecast", params=p)
        for r in (cur, fc):
            msg = {401: "OpenWeatherMap rejected the API key (401).", 429: "OpenWeatherMap rate limit reached (429).",
                   404: "Location not found (404)."}.get(r.status_code)
            if msg:
                return _unavailable(msg)
            r.raise_for_status()
        cj, fj = cur.json(), fc.json()
        now = datetime.fromtimestamp(cj["dt"], IST)
        series = [{"time": now, "temp_c": cj["main"]["temp"], "rh": cj["main"]["humidity"],
                   "rain_mm": (cj.get("rain") or {}).get("1h", 0.0)}]
        for e in fj["list"][:17]:  # 3-hourly, ~48 h (free forecast endpoint)
            t = datetime.fromtimestamp(e["dt"], IST)
            if t > now:
                series.append({"time": t, "temp_c": e["main"]["temp"], "rh": e["main"]["humidity"],
                               "rain_mm": (e.get("rain") or {}).get("3h", 0.0)})
        return {"status": "live", "label": "Live: OpenWeatherMap (3-hourly forecast)", "source": "OpenWeatherMap",
                "fetched_at": datetime.now(IST), "series": series, "current": series[0]}
    except (httpx.HTTPError, KeyError, ValueError) as e:
        return _unavailable(f"Weather service error: {type(e).__name__}")


def get_weather(mode: str, lat: float, lon: float) -> dict:
    if mode in SCENARIOS:
        s = demo_series(mode)
        return {"status": "demo", "label": SCENARIOS[mode], "source": "AgriSentry simulated scenario",
                "fetched_at": datetime.now(IST), "series": s, "current": s[0]}
    if mode == "live":
        return live_weather(lat, lon)
    raise ValueError(f"Unknown weather mode '{mode}'")
