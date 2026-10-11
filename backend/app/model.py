"""ONNX EfficientNetV2-S leaf classifier. Session is created once and reused."""
from __future__ import annotations
import io
import json
import threading
import time
import numpy as np
from PIL import Image, UnidentifiedImageError
from . import config

LOW_CONFIDENCE = 0.50
MIN_SIDE = 64
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}

_lock = threading.Lock()
_state: dict = {"session": None, "classes": None, "mean": None, "std": None, "size": 224, "error": None, "loaded": False}


class ImageRejected(ValueError):
    pass


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
            _state["error"] = f"{type(e).__name__}: {e}"
        return _state


def status() -> dict:
    s = load()
    return {"available": s["session"] is not None, "model": "efficientnet_v2_s", "error": s["error"],
            "num_classes": len(s["classes"]) if s["classes"] else None}


def parse_label(label: str) -> tuple[str, str]:
    crop, _, cond = label.partition("___")
    return crop.replace("_", " ").replace("(including sour)", "").strip(" ,"), cond.replace("_", " ").strip()


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
    if min(img.size) < MIN_SIDE:
        raise ImageRejected(f"Image is too small ({img.size[0]}×{img.size[1]}px); minimum side is {MIN_SIDE}px.")
    img = img.convert("RGB").resize((s["size"], s["size"]), Image.BILINEAR)
    arr = (np.asarray(img, dtype=np.float32) / 255.0 - s["mean"]) / s["std"]
    return arr.transpose(2, 0, 1)[None].astype(np.float32)


def softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()


def classify(data: bytes) -> dict:
    s = load()
    if s["session"] is None:
        return {"status": "unavailable", "error": f"Model unavailable: {s['error']}"}
    tensor = preprocess(data)  # may raise ImageRejected
    t0 = time.perf_counter()
    logits = s["session"].run(None, {s["input_name"]: tensor})[0][0]
    latency = (time.perf_counter() - t0) * 1000
    probs = softmax(logits.astype(np.float64))
    order = np.argsort(-probs)[:3]
    top = [{"label": s["classes"][i], "crop": parse_label(s["classes"][i])[0],
            "condition": parse_label(s["classes"][i])[1], "score": float(probs[i])} for i in order]
    best = top[0]
    return {"status": "ok", "label": best["label"], "crop": best["crop"], "condition": best["condition"],
            "score": best["score"], "top3": top, "latency_ms": round(latency, 1),
            "is_tomato": best["crop"].lower() == "tomato", "low_confidence": best["score"] < LOW_CONFIDENCE,
            "score_note": "Softmax score of the model's top class — not a calibrated probability of infection."}
