"""Calibrate photo-quality thresholds on PlantDoc field photos and synthetically degraded copies.

Outputs percentiles of each metric for: originals, Gaussian-blurred copies (radius 2 and 4 px at 512 px),
and darkened copies (x0.35, x0.15), plus model accuracy by metric quartile (from data/eval/plantdoc_eval.json).
Writes data/eval/quality_calibration.json.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app import quality  # noqa: E402

samples = ROOT / "data" / "plantdoc_samples"
files = sorted(p for p in samples.rglob("*") if p.is_file())


def norm(img):
    s = 512 / max(img.size)
    return img.resize((round(img.width * s), round(img.height * s)), Image.BILINEAR) if s < 1 else img


variants = {"original": [], "blur_r2": [], "blur_r4": [], "dark_x0.35": [], "dark_x0.15": []}
per_file = {}
for f in files:
    try:
        img = norm(ImageOps.exif_transpose(Image.open(f)).convert("RGB"))
    except Exception:
        continue
    m = quality.metrics(img)
    per_file[f"{f.parent.name}/{f.name}"] = m
    variants["original"].append(m)
    variants["blur_r2"].append(quality.metrics(img.filter(ImageFilter.GaussianBlur(2))))
    variants["blur_r4"].append(quality.metrics(img.filter(ImageFilter.GaussianBlur(4))))
    variants["dark_x0.35"].append(quality.metrics(ImageEnhance.Brightness(img).enhance(0.35)))
    variants["dark_x0.15"].append(quality.metrics(ImageEnhance.Brightness(img).enhance(0.15)))

pcts = [1, 5, 10, 25, 50, 75, 90, 95, 99]
summary = {}
for name, ms in variants.items():
    summary[name] = {k: {f"p{p}": round(float(np.percentile([m[k] for m in ms], p)), 4) for p in pcts}
                     for k in ("sharpness", "brightness", "detail_retained", "overexposed")}

T = quality.THRESHOLDS
def rate(ms, key, thr, below=True):
    return round(sum((m[key] < thr) if below else (m[key] > thr) for m in ms) / len(ms), 3)

flag_rates = {name: {"sharpness<fail": rate(ms, "sharpness", T["sharpness_fail"]), "sharpness<warn": rate(ms, "sharpness", T["sharpness_warn"]),
                     "brightness<fail": rate(ms, "brightness", T["brightness_fail"]), "brightness<warn": rate(ms, "brightness", T["brightness_warn"])}
              for name, ms in variants.items()}

# Does the model do worse on photos the checks would flag? (crop-conditioned correctness from the evaluation)
acc = {}
ev = ROOT / "data" / "eval" / "plantdoc_eval.json"
if ev.exists():
    rows = [r for r in json.loads(ev.read_text(encoding="utf-8"))["rows"] if not r["single_class_crop"] and r["file"] in per_file]
    for key in ("sharpness", "detail_retained", "brightness"):
        vals = np.array([per_file[r["file"]][key] for r in rows])
        ok = np.array([r["pred_conditioned"] == r["truth"] for r in rows])
        qs = np.percentile(vals, [25, 50, 75])
        bins = np.digitize(vals, qs)
        acc[key] = [{"quartile": i + 1, "range": [round(float(vals[bins == i].min()), 3), round(float(vals[bins == i].max()), 3)],
                     "n": int((bins == i).sum()), "accuracy": round(float(ok[bins == i].mean()), 3)} for i in range(4)]

out = {"images": len(variants["original"]), "thresholds": T, "percentiles": summary, "flag_rates": flag_rates, "accuracy_by_quartile": acc}
(ROOT / "data" / "eval").mkdir(parents=True, exist_ok=True)
(ROOT / "data" / "eval" / "quality_calibration.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps({k: out[k] for k in ("images", "flag_rates", "accuracy_by_quartile")}, indent=1))
for name in variants:
    print(name, {k: (v["p5"], v["p50"], v["p95"]) for k, v in summary[name].items()})
