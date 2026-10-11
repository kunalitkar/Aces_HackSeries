"""Farmer-facing advisory. Every statement is derived from the risk assessment, the image result and the catalogue.

Severity is reported as unavailable: AgriSentry has no validated lesion-area method.
"""
from __future__ import annotations
from . import catalog

SEVERITY = {"available": False,
            "text": "Visual severity is not estimated. AgriSentry has no validated lesion-measurement method, and model confidence is not severity.",
            "manual": "Estimate it yourself: check 20 plants spread across the field, count plants with symptoms, and note roughly what share of leaves on affected plants show lesions."}
CONSULT = ("Before applying any pesticide, confirm the problem with your local Krishi Vigyan Kendra (KVK) or agriculture officer "
           "and follow their product and dose advice. AgriSentry does not recommend specific chemicals or doses.")
LEVEL_ORDER = ["info", "watch", "warning", "alert"]


def _raise(cur: str, new: str) -> str:
    return new if LEVEL_ORDER.index(new) > LEVEL_ORDER.index(cur) else cur


def _weather(risk: dict | None) -> tuple[str, str, bool]:
    """(text, category-or-state, high?)"""
    if not risk or risk.get("status") == "unavailable":
        return "Weather risk is unavailable right now; only the leaf image (if any) informs this advice.", "unknown", False
    if risk["status"] == "not_applicable":
        return risk["reason"], "not_applicable", False
    cat, idx = risk["category"], risk["index"]
    p48 = risk.get("peak_48h")
    when = (f" Within 48 h it is forecast to reach about {p48['index']:.0f}/100 ({p48['category']}) around "
            f"{p48['time'].strftime('%a %H:%M')}.") if p48 and p48["index"] > idx + 5 else ""
    high = cat in ("High", "Very High") or bool(p48 and p48["category"] in ("High", "Very High"))
    lead = {"Low": "not very favourable", "Moderate": "moderately favourable", "High": "highly favourable", "Very High": "very highly favourable"}[cat]
    stale = " The weather observation is stale; refresh before acting." if risk.get("stale") else ""
    return f"Weather over the next 12 h is {lead} for late blight ({idx:.0f}/100).{when}{stale}", cat, high


def build(risk: dict | None, image: dict | None, crop: str | None = None) -> dict:
    crop = crop or (image or {}).get("selected_crop") or "Tomato"
    w_text, w_state, high = _weather(risk)
    level, headline = "info", "Routine monitoring"
    evidence: list[dict] = []
    inspect = [f"Walk the {crop.lower()} field and look closely at older, lower leaves and stems."]
    actions = ["Keep foliage dry where possible (drip irrigation, avoid evening overhead watering) and keep good airflow."]
    finding = None

    if image and image.get("status") == "ok":
        cond, score, label = image["condition"], image["score"], image["label"]
        info = catalog.entry(label)
        if image.get("single_class_crop"):
            img_text = (f"The model has only one class for {image['crop']} ('{cond}'), so it cannot tell healthy from diseased leaves "
                        f"for this crop (raw score {score:.0%}). Use field inspection instead.")
            level, headline = "watch", "Image screening is limited for this crop"
        elif image.get("crop_mismatch"):
            alt = image["unrestricted_top3"][0]
            img_text = (f"The photo does not look like {image['selected_crop']} to the model (only {image['crop_mass']:.0%} of its score "
                        f"went to {image['selected_crop']} classes; it looked most like {alt['crop']} – {alt['condition']}). "
                        "Check the crop selection or retake a clear photo of one leaf.")
            level, headline = "watch", "Image uncertain – retake photo"
        elif image.get("low_confidence"):
            img_text = (f"The model is unsure (top guess '{cond}', score {score:.0%}). Retake a sharp, well-lit close-up of a single leaf "
                        "against a plain background, or assess the plant manually.")
            level, headline = "watch", "Image uncertain – retake photo"
        elif image.get("healthy"):
            img_text = f"The image model predicts a healthy {image['crop'].lower()} leaf (score {score:.0%}). This describes only the photographed leaf."
            finding = "healthy"
        else:
            finding = label
            img_text = f"The image model's top prediction is {image['crop'].lower()} {cond.lower()} (score {score:.0%}). This is AI screening, not a diagnosis."
            urgent = bool(info and info.get("urgent"))
            late_blight = cond.lower() == "late blight"
            if late_blight and high:
                level, headline = "alert", "Late-blight pattern and favourable weather – inspect today"
            elif urgent:
                level, headline = "warning", f"Possible {cond.lower()} – inspect today"
            else:
                level, headline = "warning", f"Possible {cond.lower()} – verify in the field"
            if info:
                inspect = [f"Look for: {info['look_for']}", "Check neighbouring plants and note how many show the same signs."]
                actions = list(info["prevent"])
            if late_blight is False and w_state not in ("not_applicable", "unknown"):
                img_text += " Note: the weather index covers late blight only, not this condition."
            if w_state == "Low" and not high:
                img_text += " Low weather risk does not cancel a suspicious image — still inspect the plant."
        evidence.append({"source": "image", "text": img_text})
    elif image and image.get("status") == "unavailable":
        evidence.append({"source": "image", "text": "Leaf-image classification is unavailable; the weather assessment still applies."})
    else:
        evidence.append({"source": "image", "text": "No leaf image has been analysed yet."})

    evidence.append({"source": "weather", "text": w_text})
    if high and finding in (None, "healthy") and level in ("info", "watch"):
        level = _raise(level, "watch")
        headline = ("Leaf looks healthy, but weather favours late blight" if finding == "healthy"
                    else "Weather favours late blight – scout your crop")
        inspect.append("Symptoms may not be visible yet: scout early in the morning (when dew is present) across 10–20 plants, daily while conditions persist.")
        late = catalog.entry(f"{'Potato' if crop.lower() == 'potato' else 'Tomato'}___Late_blight")
        inspect.append(f"Late-blight signs: {late['look_for']}")
    elif w_state == "Moderate" and level == "info":
        level, headline = "watch", "Moderate late-blight favourability – stay alert"
    elif w_state == "unknown" and level == "info" and not finding:
        headline = "Weather risk unavailable"
    elif w_state == "not_applicable" and level == "info" and finding == "healthy":
        actions = list(catalog.HEALTHY["prevent"])
    evidence.append({"source": "severity", "text": SEVERITY["text"]})

    why = " ".join(e["text"] for e in evidence[:2])
    if risk and risk.get("status") == "ok":
        top = sorted(risk["factors"], key=lambda f: -f["points"] / f["max_points"])[:2]
        why += " Main weather contributors: " + "; ".join(f"{f['label'].lower()} ({f['detail']})" for f in top) + "."
    why += " Favourable weather raises the chance of disease developing but does not confirm infection."

    return {
        "level": level, "headline": headline, "crop": crop, "evidence": evidence,
        "what_is_happening": " ".join(e["text"] for e in evidence[:2]),
        "why": why, "inspect": inspect, "actions": actions,
        "reassess": ("Re-check within 24 h and after each forecast update while conditions stay favourable."
                     if level in ("watch", "warning", "alert") else "Re-check at your next routine scouting (every 3–7 days) or after rain."),
        "consult": CONSULT, "severity": SEVERITY, "references": catalog.GENERAL_REFERENCES,
    }
