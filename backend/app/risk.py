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
    factors = [
        {"key": "duration", "label": "Favourable-hours run", "points": f_dur, "max_points": 50, "available": True,
         "detail": f"Longest unbroken favourable run: {best:.0f} h (full score at {FULL_RUN_H:.0f} h)"},
        {"key": "temperature", "label": "Temperature suitability", "points": f_temp, "max_points": 20, "available": True,
         "detail": f"Mean {sum(temps)/len(temps):.1f}°C; most favourable 15–22°C, none below 10°C or above 27°C"},
        {"key": "humidity", "label": "Relative humidity", "points": f_hum, "max_points": 20, "available": True,
         "detail": f"Mean RH {sum(rhs)/len(rhs):.0f}%; scoring rises from 70% towards 95%"},
        {"key": "rain", "label": "Rainfall / leaf wetness", "points": f_rain, "max_points": 10, "available": bool(rain_vals),
         "detail": (f"{rain_total:.1f} mm in window (full score at {RAIN_FULL_MM:.0f} mm)" if rain_vals
                    else "Rainfall data missing; factor flagged unavailable (contributes 0)")},
    ]
    return {"index": round(sum(f["points"] for f in factors), 1), "factors": factors,
            "coverage": len(valid) / len(pts), "longest_run_h": best, "rain_total_mm": round(rain_total, 2),
            "mean_temp": sum(temps) / len(temps), "mean_rh": sum(rhs) / len(rhs)}


def assess(points: list[dict]) -> dict:
    """Assess a weather series [{time, temp_c, rh, rain_mm}] (rain_mm may be None)."""
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
                          "temp_c": p.get("temp_c"), "rh": p.get("rh"), "rain_mm": p.get("rain_mm")})
    peak = max(trend, key=lambda t: t["index"]) if trend else None
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
    return {"status": "ok", "index": idx, "category": cat, "factors": head["factors"], "trend": trend,
            "peak": peak, "window_hours": WINDOW_H, "coverage": round(head["coverage"], 2),
            "explanation": explanation,
            "method": "Heuristic late-blight favourability (Smith-period-inspired); not a validated outbreak probability."}
