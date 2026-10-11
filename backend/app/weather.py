from __future__ import annotations
import logging
import math
import time
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
        out.append({"time": t, "temp_c": round(temp, 1), "rh": round(min(rh, 99)), "rain_mm": rain, "kind": "simulated"})
    return out


def _unavailable(error: str, hint: str | None = None) -> dict:
    return {"status": "unavailable", "label": "Live weather unavailable", "error": error, "hint": hint,
            "source": "OpenWeatherMap", "fetched_at": datetime.now(IST)}


# Short-lived cache so repeated renders / tab switches do not hit the API. Only successes are cached.
CACHE_TTL_S = 300
_cache: dict[tuple[float, float], tuple[float, dict]] = {}
logging.getLogger("httpx").setLevel(logging.WARNING)  # httpx INFO logs would print the appid in URLs

OWM = "https://api.openweathermap.org/data/2.5"
HTTP_ERRORS = {
    401: ("OpenWeatherMap rejected the API key (HTTP 401).",
          "The key is invalid, or it was created recently — new keys can take up to 2 hours to activate. Check OPENWEATHER_API_KEY in backend/.env."),
    404: ("OpenWeatherMap could not find this location (HTTP 404).", "Check the farm's latitude/longitude."),
    429: ("OpenWeatherMap rate limit reached (HTTP 429).", "Wait a minute and press Refresh. The free plan allows 60 calls/minute."),
}


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _point(time: datetime, main: dict, wind: dict | None, wx: list | None, rain_mm, pop=None, kind="forecast") -> dict:
    w0 = wx[0] if isinstance(wx, list) and wx and isinstance(wx[0], dict) else {}
    return {"time": time, "temp_c": _num(main.get("temp")), "feels_like_c": _num(main.get("feels_like")),
            "rh": _num(main.get("humidity")), "pressure_hpa": _num(main.get("pressure")),
            "wind_ms": _num((wind or {}).get("speed")), "condition": w0.get("main"), "description": w0.get("description"),
            "icon": w0.get("icon"), "rain_mm": rain_mm, "pop": _num(pop), "kind": kind}


def _fetch_live(lat: float, lon: float) -> dict:
    if not config.OWM_API_KEY:
        return _unavailable("OPENWEATHER_API_KEY is not configured on the server.",
                            "Create backend/.env containing OPENWEATHER_API_KEY=<your key> and restart the backend.")
    params = {"lat": lat, "lon": lon, "units": "metric", "appid": config.OWM_API_KEY}
    try:
        with httpx.Client(timeout=httpx.Timeout(8.0, connect=5.0)) as c:
            cur = c.get(f"{OWM}/weather", params=params)
            fc = c.get(f"{OWM}/forecast", params=params)
        for r in (cur, fc):
            if r.status_code in HTTP_ERRORS:
                return _unavailable(*HTTP_ERRORS[r.status_code])
            if r.status_code >= 400:
                return _unavailable(f"OpenWeatherMap returned HTTP {r.status_code}.")
        cj, fj = cur.json(), fc.json()
        offset = int(cj.get("timezone", (fj.get("city") or {}).get("timezone", 0)) or 0)
        tz = timezone(timedelta(seconds=offset))
        now = datetime.fromtimestamp(cj["dt"], tz)
        cur_rain = (cj.get("rain") or {}).get("1h")  # OWM omits `rain` when none fell in the last hour
        current = _point(now, cj["main"], cj.get("wind"), cj.get("weather"), cur_rain if cur_rain is not None else 0.0, kind="observed")
        series = [current]
        for e in fj["list"]:  # 40 entries x 3 h = 5 days
            t = datetime.fromtimestamp(e["dt"], tz)
            if t > now:
                series.append(_point(t, e["main"], e.get("wind"), e.get("weather"),
                                     (e.get("rain") or {}).get("3h", 0.0), e.get("pop")))
        city = fj.get("city") or {}
        return {"status": "live", "label": "Live: OpenWeatherMap (current + 5-day / 3-hour forecast)", "source": "OpenWeatherMap",
                "fetched_at": datetime.now(timezone.utc).astimezone(tz), "observed_at": now, "utc_offset_seconds": offset,
                "location": {"name": cj.get("name") or city.get("name") or None, "country": (cj.get("sys") or {}).get("country") or city.get("country"),
                             "lat": (cj.get("coord") or {}).get("lat", lat), "lon": (cj.get("coord") or {}).get("lon", lon)},
                "series": series, "current": current}
    except httpx.TimeoutException:
        return _unavailable("The weather service timed out.", "Check your internet connection and press Refresh.")
    except httpx.HTTPError as e:
        return _unavailable(f"Could not reach OpenWeatherMap ({type(e).__name__}).", "Check your internet connection.")
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        return _unavailable(f"OpenWeatherMap returned an unexpected response ({type(e).__name__}).")


def live_weather(lat: float, lon: float, refresh: bool = False) -> dict:
    key = (round(lat, 3), round(lon, 3))
    hit = _cache.get(key)
    if hit and not refresh and time.monotonic() - hit[0] < CACHE_TTL_S:
        return {**hit[1], "cached": True}
    res = _fetch_live(lat, lon)
    if res["status"] == "live":
        _cache[key] = (time.monotonic(), res)
    return {**res, "cached": False}


def geocode(query: str) -> dict:
    """City/place search via OpenWeatherMap Geocoding API (same key, through the backend only)."""
    q = query.strip()
    if len(q) < 2:
        return {"status": "error", "error": "Type at least 2 characters.", "results": []}
    if not config.OWM_API_KEY:
        return {"status": "error", "error": "Location search needs OPENWEATHER_API_KEY on the server.", "results": []}
    try:
        with httpx.Client(timeout=httpx.Timeout(8.0, connect=5.0)) as c:
            r = c.get("https://api.openweathermap.org/geo/1.0/direct", params={"q": q, "limit": 5, "appid": config.OWM_API_KEY})
        if r.status_code in HTTP_ERRORS:
            return {"status": "error", "error": HTTP_ERRORS[r.status_code][0], "results": []}
        r.raise_for_status()
        rows = r.json()
        results = [{"name": x["name"], "state": x.get("state"), "country": x.get("country"),
                    "lat": float(x["lat"]), "lon": float(x["lon"])} for x in rows]
        return {"status": "ok", "results": results,
                "error": None if results else f"No place found for '{q}'. Try adding the state, e.g. 'Nashik, Maharashtra'."}
    except httpx.TimeoutException:
        return {"status": "error", "error": "Location search timed out.", "results": []}
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as e:
        return {"status": "error", "error": f"Location search failed ({type(e).__name__}).", "results": []}


def get_weather(mode: str, lat: float, lon: float, refresh: bool = False) -> dict:
    if mode in SCENARIOS:
        s = demo_series(mode)
        return {"status": "demo", "label": SCENARIOS[mode], "source": "AgriSentry simulated scenario",
                "fetched_at": datetime.now(IST), "observed_at": s[0]["time"], "utc_offset_seconds": 19800, "series": s, "current": s[0]}
    if mode == "live":
        return live_weather(lat, lon, refresh)
    raise ValueError(f"Unknown weather mode '{mode}'")
