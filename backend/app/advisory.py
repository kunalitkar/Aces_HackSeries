"""Farmer-facing advisory. Every statement derives from the risk assessment and/or image result."""
from __future__ import annotations

CONSULT = ("Late blight can destroy a crop within days. If you see water-soaked, dark lesions with pale fuzzy growth, "
           "contact your local Krishi Vigyan Kendra (KVK) or agriculture officer before applying any fungicide.")


def _weather_part(risk: dict | None) -> tuple[str, str]:
    if not risk or risk.get("status") != "ok":
        return ("Weather risk is unavailable right now, so only the leaf image (if any) can inform this advice.", "unknown")
    cat, idx = risk["category"], risk["index"]
    peak = risk.get("peak")
    when = f" Peak favourability (~{peak['index']:.0f}/100) is expected around {peak['time'].strftime('%a %H:%M')}." if peak and peak["index"] > idx + 5 else ""
    if cat in ("High", "Very High"):
        return (f"Weather is {cat.lower()}-favourability for late blight ({idx:.0f}/100): cool, humid and wet spells "
                f"support the pathogen.{when}", cat)
    if cat == "Moderate":
        return (f"Weather is moderately favourable for late blight ({idx:.0f}/100).{when}", cat)
    return (f"Weather is currently not very favourable for late blight ({idx:.0f}/100).{when}", cat)


def build(risk: dict | None, image: dict | None) -> dict:
    w_text, w_cat = _weather_part(risk)
    high = w_cat in ("High", "Very High")
    level, headline = "info", "Routine monitoring"
    img_text = "No leaf image has been analysed yet."
    inspect = ["Walk the field and check lower, older leaves and stem bases for dark, water-soaked patches."]
    action = ["Keep foliage dry where possible (drip irrigation, avoid evening overhead watering) and maintain airflow."]

    if image and image.get("status") == "ok":
        label, score = image["label"], image["score"]
        cond = image["condition"]
        if not image["is_tomato"]:
            img_text = (f"The photo looks like '{image['crop']} – {cond}', which is outside AgriSentry's tomato scope. "
                        "Treat the image result as unreliable and re-photograph a tomato leaf.")
        elif image["low_confidence"]:
            img_text = (f"The model is unsure (top guess '{cond}', score {score:.0%}). Retake a sharp, well-lit close-up "
                        "of a single leaf before drawing conclusions.")
        elif label == "Tomato___Late_blight":
            img_text = f"The image model's top prediction is tomato late blight (score {score:.0%}). This is a screening result, not a diagnosis."
            level, headline = ("alert", "Late-blight pattern detected – inspect today") if high else ("warning", "Possible late blight – verify in field")
            inspect = ["Inspect the photographed plant and neighbours today: look for greasy dark lesions, pale-white fuzz under leaves in the morning, and brown stem lesions.",
                       "Mark and check plants nearby; note how many show symptoms."]
            action = ["Isolate suspected plants; avoid moving through wet foliage so spores are not spread.",
                      "Ask a local agronomist about suitable protectant/curative fungicide before spraying."]
        elif label == "Tomato___healthy":
            img_text = f"The image model predicts a healthy tomato leaf (score {score:.0%}); this only describes the photographed leaf."
            if high:
                level, headline = "watch", "Leaf looks healthy, but weather favours blight"
                inspect.append("Symptoms may not be visible yet — re-check every day while the weather stays favourable.")
        else:
            img_text = f"The image model predicts '{cond}' (score {score:.0%}), a different tomato condition. Late blight is not the top prediction."
            level, headline = "warning", f"Possible {cond.lower()} – verify in field"
            inspect = [f"Compare the leaf with a trusted guide for {cond.lower()}; also rule out late blight if the weather stays humid."]
    elif image and image.get("status") == "unavailable":
        img_text = "Leaf-image classification is currently unavailable; the weather assessment below still applies."
    elif image:
        img_text = "The leaf image could not be analysed. Please upload a clear JPEG/PNG photo."

    if level == "info" and high:
        level, headline = "watch", "High blight-favourability weather – scout your crop"
        inspect.append("Scout early morning when dew is present; check 10–20 plants spread across the field.")
        action.append("Plan protective measures with local advice now; do not wait for symptoms if forecast stays wet and cool.")
    elif level == "info" and w_cat == "Moderate":
        level, headline = "watch", "Moderate favourability – stay alert"
    if w_cat == "unknown" and level == "info":
        headline = "Weather risk unavailable"

    low_note = ""
    if w_cat == "Low" and level in ("warning", "alert"):
        low_note = " Low weather risk does not cancel a suspicious image — still inspect the plant."

    return {
        "level": level, "headline": headline,
        "what_is_happening": f"{img_text} {w_text}".strip(),
        "why": (risk["explanation"] if risk and risk.get("status") == "ok" else "Risk could not be computed from weather data.")
               + low_note + " Favourable weather raises the chance of disease developing but does not confirm infection.",
        "inspect": inspect, "actions": action,
        "reassess": "Re-check after the next forecast update (about every 3–6 hours) and daily while conditions stay favourable; re-upload a photo if symptoms appear.",
        "consult": CONSULT,
        "severity": "Visual severity is not estimated by AgriSentry; assess lesion spread through field inspection.",
    }
