"""ONNX EfficientNetV2-S leaf classifier (BiernyVR/crop-disease-classifier, 38 PlantVillage classes).

Preprocessing follows the model card exactly: RGB, bilinear resize to 224x224, /255, ImageNet mean/std
(read from classes.json), CHW, softmax over logits. The session is created once and reused.

Crop-conditioned prediction: when the user states the crop, scores are renormalised over that crop's
classes only. `crop_mass` (the unrestricted probability assigned to the stated crop at all) is reported so
photos that do not look like the stated crop are flagged as uncertain instead of being forced into a class.
"""
from __future__ import annotations
import io
import json
import threading
import time
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from . import config

LOW_CONFIDENCE = 0.50      # top score below this -> "uncertain"
CROP_MISMATCH = 0.50       # stated crop receives < 50 % of unrestricted probability -> "photo may not be this crop"
MIN_SIDE = 64
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}

_lock = threading.Lock()
_state: dict = {"session": None, "classes": None, "mean": None, "std": None, "size": 224, "error": None, "loaded": False}


class ImageRejected(ValueError):
    pass


def parse_label(label: str) -> tuple[str, str]:
    crop, _, cond = label.partition("___")
    crop = crop.replace("_(including_sour)", "").replace("_(maize)", "").replace(",_bell", " (bell)").replace("_", " ").strip()
    if crop == "Pepper (bell)":
        crop = "Bell pepper"
    return crop, cond.replace("_", " ").strip()


def load() -> dict:
    with _lock:
        if _state["loaded"]:
            return _state
        _state["loaded"] = True
        try:
            import onnxruntime as ort
            meta = json.loads(config.CLASSES_PATH.read_text(encoding="utf-8"))
            classes = meta["classes"]
            sess = ort.InferenceSession(str(config.MODEL_PATH), providers=["CPUExecutionProvider"])
            out_dim = sess.get_outputs()[0].shape[-1]
            if out_dim != len(classes):
                raise RuntimeError(f"Model outputs {out_dim} classes but classes.json lists {len(classes)}")
            _state.update(session=sess, classes=classes, size=int(meta.get("image_size", 224)),
                          mean=np.array(meta["normalisation"]["mean"], dtype=np.float32),
                          std=np.array(meta["normalisation"]["std"], dtype=np.float32),
                          input_name=sess.get_inputs()[0].name)
        except Exception as e:  # missing files, bad onnxruntime install, etc.
            hint = " Run backend/scripts/download_model.py to fetch the weights." if isinstance(e, (FileNotFoundError, OSError)) else ""
            _state["error"] = f"{type(e).__name__}: {e}.{hint}"
        return _state


def status() -> dict:
    s = load()
    return {"available": s["session"] is not None, "model": "efficientnet_v2_s", "version": config.MODEL_VERSION,
            "error": s["error"], "num_classes": len(s["classes"]) if s["classes"] else None}


def class_catalog() -> list[dict]:
    """Crops and their classes, derived from the loaded classes.json (never hardcoded)."""
    s = load()
    crops: dict[str, list[dict]] = {}
    for i, label in enumerate(s["classes"] or []):
        crop, cond = parse_label(label)
        crops.setdefault(crop, []).append({"index": i, "label": label, "condition": cond, "healthy": cond.lower() == "healthy"})
    return [{"crop": c, "classes": v, "has_healthy_class": any(x["healthy"] for x in v),
             "disease_classes": sum(not x["healthy"] for x in v)} for c, v in crops.items()]


def preprocess(data: bytes) -> np.ndarray:
    s = load()
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ImageRejected("File is not a readable image. Upload a JPEG, PNG or WebP photo.")
    if fmt not in ALLOWED_FORMATS:
        raise ImageRejected(f"Unsupported image format '{fmt}'. Use JPEG, PNG or WebP.")
    img = ImageOps.exif_transpose(img)  # phone photos store rotation in EXIF
    if min(img.size) < MIN_SIDE:
        raise ImageRejected(f"Image is too small ({img.size[0]}×{img.size[1]}px); minimum side is {MIN_SIDE}px.")
    img = img.convert("RGB").resize((s["size"], s["size"]), Image.BILINEAR)
    arr = (np.asarray(img, dtype=np.float32) / 255.0 - s["mean"]) / s["std"]
    return arr.transpose(2, 0, 1)[None].astype(np.float32)


def softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()


def _entry(i: int, score: float) -> dict:
    label = _state["classes"][i]
    crop, cond = parse_label(label)
    return {"label": label, "crop": crop, "condition": cond, "healthy": cond.lower() == "healthy", "score": float(score)}


def predict_probs(data: bytes) -> tuple[np.ndarray, float]:
    s = load()
    tensor = preprocess(data)  # may raise ImageRejected
    t0 = time.perf_counter()
    logits = s["session"].run(None, {s["input_name"]: tensor})[0][0]
    return softmax(logits.astype(np.float64)), (time.perf_counter() - t0) * 1000


def interpret(probs: np.ndarray, crop: str | None) -> dict:
    """Turn a probability vector into the API result, optionally conditioned on the stated crop."""
    classes = _state["classes"]
    order = np.argsort(-probs)
    unrestricted = [_entry(i, probs[i]) for i in order[:3]]
    res = {"status": "ok", "model_version": config.MODEL_VERSION, "unrestricted_top3": unrestricted,
           "selected_crop": None, "crop_mass": None, "crop_mismatch": False, "single_class_crop": False,
           "score_note": "Softmax score from the model — not a calibrated probability of infection."}
    idx = [i for i, l in enumerate(classes) if crop and parse_label(l)[0].lower() == crop.lower()]
    if crop and not idx:
        raise ImageRejected(f"'{crop}' is not supported by the model.")
    if idx:
        mass = float(probs[idx].sum())
        res.update(selected_crop=parse_label(classes[idx[0]])[0], crop_mass=mass, crop_mismatch=mass < CROP_MISMATCH)
        if len(idx) == 1:
            # Renormalising over one class would always give 100 %; report the raw score instead.
            top = [_entry(idx[0], probs[idx[0]])]
            res["single_class_crop"] = True
        else:
            sub = probs[idx] / mass
            top = [_entry(idx[j], sub[j]) for j in np.argsort(-sub)[:3]]
        res["conditioned"] = True
    else:
        top = unrestricted
        res["conditioned"] = False
    best = top[0]
    res.update(label=best["label"], crop=best["crop"], condition=best["condition"], healthy=best["healthy"],
               score=best["score"], top3=top)
    res["low_confidence"] = best["score"] < LOW_CONFIDENCE
    res["uncertain"] = bool(res["low_confidence"] or res["crop_mismatch"] or res["single_class_crop"])
    return res


def classify(data: bytes, crop: str | None = None) -> dict:
    s = load()
    if s["session"] is None:
        return {"status": "unavailable", "error": f"Model unavailable: {s['error']}"}
    probs, latency = predict_probs(data)
    res = interpret(probs, crop)
    res["latency_ms"] = round(latency, 1)
    return res
