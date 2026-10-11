"""Lightweight photo-quality checks run before inference.

These are image-statistics heuristics. They can say a photo is blurry, dark, low-resolution or that fine
detail is lost at the model's 224x224 input; they CANNOT tell whether a leaf is present or whether the photo
is suitable for diagnosis. Thresholds live in THRESHOLDS (overridable via environment variables) and were
calibrated by scripts/calibrate_quality.py on PlantDoc field photos and degraded copies of them.
"""
from __future__ import annotations
import os
import numpy as np
from PIL import Image

ANALYSIS_SIDE = 512  # images are measured at a fixed scale so the sharpness numbers are comparable


def _env(name: str, default: float) -> float:
    try:
        return float(os.getenv(f"AGRISENTRY_QC_{name}", "").strip() or default)
    except ValueError:
        return default


# fail = conclusively poor (inference blocked unless the farmer chooses to continue); warn = questionable.
# Calibration (data/eval/quality_calibration.json, 236 PlantDoc photos): sharpness of originals p1 = 60, of
# Gaussian-blurred copies (r=2 px at 512 px) p95 = 13.5; brightness of originals min = 54, of x0.15-darkened
# copies p95 = 33; near-white fraction of originals p99 = 0.82 (many white backgrounds).
THRESHOLDS = {
    "sharpness_fail": _env("SHARPNESS_FAIL", 15.0),
    "sharpness_warn": _env("SHARPNESS_WARN", 40.0),
    "brightness_fail": _env("BRIGHTNESS_FAIL", 35.0),
    "brightness_warn": _env("BRIGHTNESS_WARN", 60.0),
    "overexposed_warn": _env("OVEREXPOSED_WARN", 0.85),  # fraction of near-white pixels
    "resolution_warn": _env("RESOLUTION_WARN", 224.0),   # shortest side below the model input size
}
# Not used as a check: "detail_retained" (fine detail surviving the 224x224 resize) was tested as a
# "leaf too far away" signal, but on PlantDoc the lowest-detail quartile had the HIGHEST accuracy (49 % vs 28 %),
# so it is reported in metrics only.

MESSAGES = {
    "sharpness_fail": "The photo is blurry. Please hold the phone steady and take another photo.",
    "sharpness_warn": "The photo may be slightly blurry. If you can, take a sharper photo.",
    "brightness_fail": "The photo is too dark. Try again in better light (daylight, not direct shadow).",
    "brightness_warn": "The photo is quite dark. Better light will make spots easier to see.",
    "overexposed_warn": "Much of the photo is washed out by bright light. Try shading the leaf or changing angle.",
    "resolution_warn": "The photo is small. A larger, closer photo shows more leaf detail.",
}


def _laplacian_var(g: np.ndarray) -> float:
    lap = g[1:-1, :-2] + g[1:-1, 2:] + g[:-2, 1:-1] + g[2:, 1:-1] - 4 * g[1:-1, 1:-1]
    return float(lap.var())


def metrics(img: Image.Image) -> dict:
    """Raw measurements (img must already be EXIF-rotated)."""
    w, h = img.size
    gray = img.convert("L")
    scale = ANALYSIS_SIDE / max(w, h)
    if scale < 1:
        gray = gray.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.BILINEAR)
    g = np.asarray(gray, dtype=np.float64)
    sharp = _laplacian_var(g)
    # Fine detail that survives the model's 224x224 resize: downsample, upsample back, compare Laplacian energy.
    small = gray.resize((224, 224), Image.BILINEAR).resize(gray.size, Image.BILINEAR)
    retained = _laplacian_var(np.asarray(small, dtype=np.float64))
    return {"width": w, "height": h, "sharpness": round(sharp, 2), "brightness": round(float(g.mean()), 2),
            "overexposed": round(float((g >= 250).mean()), 4),
            "detail_retained": round(retained / sharp, 4) if sharp > 0 else 0.0}


def assess(img: Image.Image, t: dict | None = None) -> dict:
    t = t or THRESHOLDS
    m = metrics(img)
    checks = []

    def add(key: str, status: str, value: float):
        checks.append({"key": key, "status": status, "value": value, "message": MESSAGES[f"{key}_{status}"]})

    if m["sharpness"] < t["sharpness_fail"]:
        add("sharpness", "fail", m["sharpness"])
    elif m["sharpness"] < t["sharpness_warn"]:
        add("sharpness", "warn", m["sharpness"])
    if m["brightness"] < t["brightness_fail"]:
        add("brightness", "fail", m["brightness"])
    elif m["brightness"] < t["brightness_warn"]:
        add("brightness", "warn", m["brightness"])
    if m["overexposed"] > t["overexposed_warn"]:
        add("overexposed", "warn", m["overexposed"])
    if min(m["width"], m["height"]) < t["resolution_warn"]:
        add("resolution", "warn", min(m["width"], m["height"]))
    status = "fail" if any(c["status"] == "fail" for c in checks) else "warn" if checks else "ok"
    return {"status": status, "checks": checks, "metrics": m,
            "note": "Automatic checks of sharpness, light and size only; they cannot confirm that a leaf is visible."}
