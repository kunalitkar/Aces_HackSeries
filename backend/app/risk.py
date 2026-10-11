"""Transparent weather-favourability engine for tomato late blight (Phytophthora infestans).

This is a heuristic *favourability* index (0-100), NOT a validated outbreak probability
and NOT evidence of infection. Rules are inspired by classical forecasting ideas
(Smith-period style: sustained high humidity + mild temperature). Assumptions:

  favourable step   : 10 <= T <= 27 degC AND leaf-wetness proxy true
  leaf-wetness proxy: RH >= 90 %  OR  (rain >= 0.2 mm in the step AND RH >= 80 %)
  reference run     : 11 consecutive favourable hours -> full duration score

Index = duration(0-50) + temperature suitability(0-20) + humidity(0-20) + rain(0-10),
evaluated over a forward-looking 12 h window. Thresholds are documented heuristics
that need agronomist review before field use.

Missing values: points lacking temperature or humidity are skipped (never zero-filled);
if fewer than half of the points are usable the assessment is "unavailable". A series
with no rainfall data at all has its rain factor flagged unavailable.
"""
from __future__ import annotations
from datetime import timedelta

WINDOW_H = 12
T_MIN, T_MAX = 10.0, 27.0
RH_WET = 90.0
FULL_RUN_H = 11.0
RAIN_FULL_MM = 5.0
MAX_PTS = {"duration": 50, "temperature": 20, "humidity": 20, "rain": 10}
STALE_AFTER_H = 3.0  # an "observation" older than this is flagged stale

# Phytophthora infestans causes late blight in both tomato and potato; Smith-period ideas were developed for
# potato. No other crop/disease gets a weather model: applying these rules elsewhere would be unfounded.
APPLICABLE = {"tomato": "Late blight", "potato": "Late blight"}

RULES = {
    "disease": "Late blight (Phytophthora infestans), tomato and potato",
    "status": "Experimental decision support; thresholds are documented heuristics, not a validated outbreak model",
    "favourable_interval": f"{T_MIN:.0f}–{T_MAX:.0f} °C AND leaf-wetness proxy",
    "leaf_wetness_proxy": f"RH ≥ {RH_WET:.0f} %, or rain ≥ 0.2 mm in the interval with RH ≥ 80 %",
    "window": f"next {WINDOW_H} h from each time point",
    "components": [
        {"key": "duration", "max": MAX_PTS["duration"], "rule": f"longest unbroken favourable run; full score at {FULL_RUN_H:.0f} h (Smith-period length)"},
        {"key": "temperature", "max": MAX_PTS["temperature"], "rule": "mean suitability: 1 at 15–22 °C, linear to 0 at 10 °C and 27 °C"},
        {"key": "humidity", "max": MAX_PTS["humidity"], "rule": "mean of (RH − 70) / 25, clipped to 0–1"},
        {"key": "rain", "max": MAX_PTS["rain"], "rule": f"total rain in window / {RAIN_FULL_MM:.0f} mm, clipped to 0–1"},
    ],
    "categories": "Low < 25 ≤ Moderate < 50 ≤ High < 75 ≤ Very High",
    "missing_data": "points without temperature or humidity are skipped; < 50 % usable points → unavailable",
}


LEVEL_TEXT = {
    "Low": "Weather is currently less favourable for late blight. Continue normal monitoring.",
    "Moderate": "Some conditions may favour late blight. Check your crop regularly.",
    "High": "Weather may favour late blight. Inspect your crop carefully.",
    "Very High": "Conditions are strongly favourable for late blight according to this model. Inspect your crop promptly and ask a local agriculture expert if you see symptoms.",
}
DAY_ACTION = {
    "Low": "Normal monitoring.",
    "Moderate": "Check the crop during the day.",
    "High": "Inspect leaves carefully, especially lower leaves.",
    "Very High": "Inspect promptly; seek local advice if you see symptoms.",
}


def daily(pts: list[dict], trend: list[dict]) -> list[dict]:
    """Per local calendar day: the highest 12 h window score starting that day, its main factor and a weather summary.

    Days are reported only from windows the engine actually scored; the first/last day may be partial."""
    days: dict = {}
    for t in trend:
        days.setdefault(t["time"].date(), {"windows": [], "points": []})["windows"].append(t)
    for p in pts:
        if p["time"].date() in days:
            days[p["time"].date()]["points"].append(p)
    out = []
    for d, v in sorted(days.items()):
        best = max(v["windows"], key=lambda t: t["index"])
        top = max(best["factors"], key=lambda f: f["points"] / f["max_points"])
        ps = v["points"]
        temps = [p["temp_c"] for p in ps if p.get("temp_c") is not None]
        rhs = [p["rh"] for p in ps if p.get("rh") is not None]
        rains = [p["rain_mm"] for p in ps if p.get("rain_mm") is not None]
        descs = [p.get("description") for p in ps if p.get("description")]
        kinds = {t["kind"] for t in v["windows"]}
        span_h = (v["windows"][-1]["time"] - v["windows"][0]["time"]).total_seconds() / 3600
        out.append({
            "date": d.isoformat(), "index": best["index"], "category": best["category"], "peak_time": best["time"],
            "main_factor": top["name"] if top["points"] > 0 else None,
            "main_factor_reading": top["interpretation"] if top["points"] > 0 else "No factor favoured late blight.",
            "action": DAY_ACTION[best["category"]],
            "weather": {"temp_min": min(temps) if temps else None, "temp_max": max(temps) if temps else None,
                        "rh_mean": round(sum(rhs) / len(rhs)) if rhs else None,
                        "rain_mm": round(sum(rains), 1) if rains else None,
                        "description": max(set(descs), key=descs.count) if descs else None},
            "basis": "simulated" if kinds == {"simulated"} else "includes current observation" if "observed" in kinds else "forecast",
            "partial": span_h < 20, "windows": len(v["windows"]),  # a full day spans 21 h (3-hourly) to 23 h (hourly)
        })
    return out


def applicable(crop: str | None) -> str | None:
    """Disease covered by the weather model for this crop, or None."""
    return APPLICABLE.get((crop or "").strip().lower())


def not_applicable(crop: str) -> dict:
    return {"status": "not_applicable", "crop": crop,
            "reason": f"AgriSentry has no validated weather-risk model for {crop}. The late-blight rules apply only to tomato and potato; "
                      "image screening is still available."}


def category(index: float) -> str:
    return "Low" if index < 25 else "Moderate" if index < 50 else "High" if index < 75 else "Very High"


def _prep(points: list[dict]) -> list[dict]:
    """Sort and attach `_step` = hours each point represents (gap to next point, 0.25-6 h)."""
    pts = sorted((dict(p) for p in points), key=lambda p: p["time"])
    for i, p in enumerate(pts):
        if i + 1 < len(pts):
            gap = (pts[i + 1]["time"] - p["time"]).total_seconds() / 3600
            p["_step"] = max(0.25, min(gap, 6.0))
        else:
            p["_step"] = pts[i - 1]["_step"] if i else 1.0
    return pts


def favourable(p: dict) -> bool | None:
    t, rh, rain = p.get("temp_c"), p.get("rh"), p.get("rain_mm")
    if t is None or rh is None:
        return None
    wet = rh >= RH_WET or (rain is not None and rain >= 0.2 and rh >= 80)
    return bool(wet and T_MIN <= t <= T_MAX)


def _temp_suit(t: float) -> float:
    if 15 <= t <= 22:
        return 1.0
    if 10 <= t < 15:
        return (t - 10) / 5
    if 22 < t <= 27:
        return (27 - t) / 5
    return 0.0


# Plain-language readings. They restate the scoring rules above in words; they add no new thresholds.
def _interp_duration(h: float) -> str:
    if h >= FULL_RUN_H:
        return f"{h:.0f} hours in a row were cool and wet: long enough for this model to count it as fully favourable ({FULL_RUN_H:.0f} h or more)."
    if h > 0:
        return f"Some cool, wet hours ({h:.0f} h in a row), but shorter than the {FULL_RUN_H:.0f} h this model treats as fully favourable."
    return "No hours were both cool enough and wet enough to favour late blight."


def _interp_temp(temps: list[float]) -> str:
    mean = sum(temps) / len(temps)
    best = sum(15 <= t <= 22 for t in temps) / len(temps)
    ok = sum(T_MIN <= t <= T_MAX for t in temps) / len(temps)
    if best >= 0.75:
        return f"Mostly within 15–22 °C, the range this model considers most favourable for late blight (average {mean:.1f} °C)."
    if ok == 0:
        return f"Always outside {T_MIN:.0f}–{T_MAX:.0f} °C, where this model considers late blight favoured (average {mean:.1f} °C)."
    return (f"Average {mean:.1f} °C; {ok:.0%} of the time within {T_MIN:.0f}–{T_MAX:.0f} °C "
            f"and {best:.0%} within the most favourable 15–22 °C.")


def _interp_rh(rh: float) -> str:
    if rh >= RH_WET:
        return f"Very humid (≥ {RH_WET:.0f} %): leaves are likely to stay wet."
    if rh >= 80:
        return "Humid: adds risk, and counts as wet when it also rains."
    if rh > 70:
        return "Moderately humid: adds a little risk in this model."
    return "Dry enough that this model adds no humidity risk (70 % or below)."


def _interp_rain(mm: float) -> str:
    if mm >= RAIN_FULL_MM:
        return f"{mm:.1f} mm of rain: plenty to keep leaves wet."
    if mm > 0:
        return f"{mm:.1f} mm of rain: some leaf wetness."
    return "No rain in this period."


def score_window(pts: list[dict]) -> dict:
    valid = [p for p in pts if p.get("temp_c") is not None and p.get("rh") is not None]
    if not pts or len(valid) / len(pts) < 0.5:
        return {"index": None, "coverage": len(valid) / len(pts) if pts else 0.0, "factors": []}
    run = best = 0.0
    for p in pts:
        if favourable(p):
            run += p["_step"]
            best = max(best, run)
        else:
            run = 0.0
    temps = [p["temp_c"] for p in valid]
    rhs = [p["rh"] for p in valid]
    rain_vals = [p["rain_mm"] for p in pts if p.get("rain_mm") is not None]
    rain_total = sum(rain_vals)
    f_dur = round(MAX_PTS["duration"] * min(best / FULL_RUN_H, 1.0), 1)
    f_temp = round(MAX_PTS["temperature"] * sum(_temp_suit(t) for t in temps) / len(temps), 1)
    f_hum = round(MAX_PTS["humidity"] * sum(min(max((h - 70) / 25, 0), 1) for h in rhs) / len(rhs), 1)
    f_rain = round(MAX_PTS["rain"] * min(rain_total / RAIN_FULL_MM, 1.0), 1) if rain_vals else 0.0
    mt, mrh = sum(temps) / len(temps), sum(rhs) / len(rhs)
    factors = [
        {"key": "duration", "label": "Favourable-hours run", "points": f_dur, "max_points": 50, "available": True,
         "name": "Cool, wet hours in a row", "value": round(best, 1), "unit": "h", "interpretation": _interp_duration(best),
         "why": "Late-blight spores need leaves that stay wet for many hours in mild weather before they can infect.",
         "detail": f"Longest unbroken favourable run: {best:.0f} h (full score at {FULL_RUN_H:.0f} h)"},
        {"key": "temperature", "label": "Temperature suitability", "points": f_temp, "max_points": 20, "available": True,
         "name": "Temperature (average)", "value": round(mt, 1), "unit": "°C", "interpretation": _interp_temp(temps),
         "why": "The late-blight pathogen grows best in mild weather; hot or very cold weather slows it down.",
         "detail": f"Mean {sum(temps)/len(temps):.1f}°C; most favourable 15–22°C, none below 10°C or above 27°C"},
        {"key": "humidity", "label": "Relative humidity", "points": f_hum, "max_points": 20, "available": True,
         "name": "Humidity (average)", "value": round(mrh), "unit": "%", "interpretation": _interp_rh(mrh),
         "why": "Very humid air keeps leaves wet and lets the pathogen produce new spores.",
         "detail": f"Mean RH {sum(rhs)/len(rhs):.0f}%; scoring rises from 70% towards 95%"},
        {"key": "rain", "label": "Rainfall / leaf wetness", "points": f_rain, "max_points": 10, "available": bool(rain_vals),
         "name": "Rain", "value": round(rain_total, 1) if rain_vals else None, "unit": "mm",
         "interpretation": _interp_rain(rain_total) if rain_vals else "Data unavailable",
         "why": "Rain wets the leaves and splashes spores from plant to plant.",
         "detail": (f"{rain_total:.1f} mm in window (full score at {RAIN_FULL_MM:.0f} mm)" if rain_vals
                    else "Rainfall data missing; factor flagged unavailable (contributes 0)")},
    ]
    return {"index": round(sum(f["points"] for f in factors), 1), "factors": factors,
            "coverage": len(valid) / len(pts), "longest_run_h": best, "rain_total_mm": round(rain_total, 2),
            "mean_temp": sum(temps) / len(temps), "mean_rh": sum(rhs) / len(rhs)}


def assess(points: list[dict], now=None) -> dict:
    """Assess a weather series [{time, temp_c, rh, rain_mm, kind?}] (rain_mm may be None).

    `now` (aware datetime) enables the staleness check on the first (observed) point."""
    if len(points) < 2:
        return {"status": "unavailable", "reason": "Not enough weather data points for a forecast-based assessment."}
    pts = _prep(points)
    window = timedelta(hours=WINDOW_H)
    head = score_window([p for p in pts if p["time"] < pts[0]["time"] + window])
    if head["index"] is None:
        return {"status": "unavailable", "reason": "Too many missing temperature/humidity values to score risk."}
    trend = []
    for p in pts:
        win = [q for q in pts if p["time"] <= q["time"] < p["time"] + window]
        # skip trailing windows that do not cover at least ~8 h of the 12 h horizon
        if len(win) < 2 or win[-1]["time"] + timedelta(hours=win[-1]["_step"]) - win[0]["time"] < timedelta(hours=8):
            continue
        s = score_window(win)
        if s["index"] is not None:
            trend.append({"time": p["time"], "index": s["index"], "category": category(s["index"]),
                          "temp_c": p.get("temp_c"), "rh": p.get("rh"), "rain_mm": p.get("rain_mm"),
                          "kind": p.get("kind", "forecast"), "factors": s["factors"]})
    peak = max(trend, key=lambda t: t["index"]) if trend else None
    peak48 = max((t for t in trend if t["time"] < pts[0]["time"] + timedelta(hours=48)), key=lambda t: t["index"], default=None)
    intervals = [{"time": p["time"], "hours": round(p["_step"], 2), "favourable": favourable(p), "kind": p.get("kind", "forecast")} for p in pts]
    age_h = (now - pts[0]["time"]).total_seconds() / 3600 if now is not None else None
    stale = age_h is not None and pts[0].get("kind") == "observed" and age_h > STALE_AFTER_H
    idx, cat = head["index"], category(head["index"])
    explanation = (
        f"Over the next {WINDOW_H} h the weather scores {idx:.0f}/100 ({cat}) for late-blight favourability: "
        f"mean temperature {head['mean_temp']:.1f}°C, mean humidity {head['mean_rh']:.0f}%, longest favourable run "
        f"{head['longest_run_h']:.0f} h"
        + (f", rain {head['rain_total_mm']:.1f} mm" if head["factors"][3]["available"] else ", rainfall unavailable")
        + ". This describes how supportive the weather is for the disease; it does not confirm infection."
    )
    if peak and peak["index"] > idx + 5:
        explanation += f" Favourability is forecast to peak near {peak['index']:.0f}/100 ({peak['category']})."
    if stale:
        explanation += f" Warning: the latest observation is {age_h:.1f} h old; refresh before acting on this result."
    head_pts = [p for p in pts if p["time"] < pts[0]["time"] + window]
    kinds = {p.get("kind", "forecast") for p in head_pts}
    basis = "simulated" if kinds == {"simulated"} else "current observation + forecast" if "observed" in kinds else "forecast"
    period = {"start": pts[0]["time"], "end": head_pts[-1]["time"] + timedelta(hours=head_pts[-1]["_step"]), "basis": basis}
    return {"status": "ok", "index": idx, "category": cat, "level_text": LEVEL_TEXT[cat], "period": period,
            "daily": daily(pts, trend), "factors": head["factors"], "trend": trend,
            "peak": peak, "peak_48h": peak48, "intervals": intervals, "favourable_hours_48h": round(sum(
                i["hours"] for i in intervals if i["favourable"] and i["time"] < pts[0]["time"] + timedelta(hours=48)), 1),
            "data_age_hours": round(age_h, 2) if age_h is not None else None, "stale": stale,
            "rules": RULES, "window_hours": WINDOW_H, "coverage": round(head["coverage"], 2),
            "explanation": explanation,
            "method": "Heuristic late-blight favourability (Smith-period-inspired); not a validated outbreak probability."}
