"""External evaluation on the PlantDoc TEST split (field photos). Not used for training or tuning.

Reports two modes from the same forward pass:
  unrestricted      - argmax over all 38 classes
  crop-conditioned  - argmax within the true crop's classes (how the app behaves when the farmer states the crop)
                      single-class crops are excluded from this mode (renormalising one class is trivially 100 %)
Writes data/eval/plantdoc_eval.json and data/eval/plantdoc_eval.md.
"""
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "scripts"))
from app import model  # noqa: E402
from fetch_plantdoc_samples import CLASS_MAP  # noqa: E402

samples = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "plantdoc_samples"
out_dir = ROOT / "data" / "eval"
model.load()
classes = model._state["classes"]
crop_classes = defaultdict(list)
for i, c in enumerate(classes):
    crop_classes[model.parse_label(c)[0]].append(i)

rows, rejected = [], []
for folder, (_remote, truth) in CLASS_MAP.items():
    for f in sorted((samples / folder).glob("*")) if (samples / folder).exists() else []:
        try:
            probs, _ = model.predict_probs(f.read_bytes())
        except model.ImageRejected as e:
            rejected.append({"file": f"{folder}/{f.name}", "reason": str(e)})
            continue
        crop = model.parse_label(truth)[0]
        cond = model.interpret(probs, crop)
        rows.append({"file": f"{folder}/{f.name}", "truth": truth, "crop": crop,
                     "pred_unrestricted": classes[int(probs.argmax())], "score_unrestricted": float(probs.max()),
                     "pred_conditioned": cond["label"], "score_conditioned": cond["score"],
                     "crop_mass": cond["crop_mass"], "single_class_crop": cond["single_class_crop"]})


def summarise(key, subset):
    per = defaultdict(lambda: [0, 0])
    conf = Counter()
    for r in subset:
        ok = r[key] == r["truth"]
        per[r["truth"]][0] += ok
        per[r["truth"]][1] += 1
        if not ok:
            conf[(r["truth"], r[key])] += 1
    correct = sum(v[0] for v in per.values())
    total = sum(v[1] for v in per.values())
    recalls = [v[0] / v[1] for v in per.values() if v[1]]
    return {"n": total, "correct": correct, "incorrect": total - correct,
            "accuracy": round(correct / total, 4) if total else None,
            "macro_recall": round(sum(recalls) / len(recalls), 4) if recalls else None,
            "per_class": {k: {"correct": v[0], "n": v[1], "recall": round(v[0] / v[1], 3)} for k, v in sorted(per.items())},
            "top_confusions": [{"truth": t, "predicted": p, "count": n} for (t, p), n in conf.most_common(12)]}


multi = [r for r in rows if not r["single_class_crop"]]
report = {
    "generated_at": datetime.now(timezone.utc).isoformat(), "model_version": model.status()["version"],
    "dataset": "PlantDoc test split (github.com/pratikkayal/PlantDoc-Dataset), images matching a model class",
    "images_evaluated": len(rows), "images_rejected": rejected,
    "unrestricted_all": summarise("pred_unrestricted", rows),
    "unrestricted_multiclass_crops": summarise("pred_unrestricted", multi),
    "crop_conditioned_multiclass_crops": summarise("pred_conditioned", multi),
    "crop_identified_correctly_unrestricted": round(sum(model.parse_label(r["pred_unrestricted"])[0] == r["crop"] for r in rows) / len(rows), 4) if rows else None,
    "rows": rows,
}
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "plantdoc_eval.json").write_text(json.dumps(report, indent=1), encoding="utf-8")

U, UM, C = report["unrestricted_all"], report["unrestricted_multiclass_crops"], report["crop_conditioned_multiclass_crops"]
md = [f"# PlantDoc external evaluation\n", f"Generated {report['generated_at']} · model `{report['model_version']}`\n",
      f"{report['dataset']}. **{len(rows)} images** evaluated, {len(rejected)} rejected by upload validation. "
      "Field photos; PlantDoc labels are image-level and somewhat noisy. Small per-class samples: treat as indicative, not a benchmark.\n",
      "| Mode | Images | Correct | Accuracy | Macro recall |", "|---|---:|---:|---:|---:|",
      f"| Unrestricted, all classes | {U['n']} | {U['correct']} | {U['accuracy']:.1%} | {U['macro_recall']:.1%} |",
      f"| Unrestricted, multi-class crops only | {UM['n']} | {UM['correct']} | {UM['accuracy']:.1%} | {UM['macro_recall']:.1%} |",
      f"| Crop-conditioned, multi-class crops | {C['n']} | {C['correct']} | {C['accuracy']:.1%} | {C['macro_recall']:.1%} |",
      f"\nCrop identified correctly (unrestricted): {report['crop_identified_correctly_unrestricted']:.1%}\n",
      "## Per class", "| True class | n | Unrestricted | Crop-conditioned |", "|---|---:|---:|---:|"]
for k, v in U["per_class"].items():
    c = C["per_class"].get(k)
    cond = f"{c['correct']}/{c['n']}" if c else "n/a (single-class crop)"
    md.append(f"| {k} | {v['n']} | {v['correct']}/{v['n']} | {cond} |")
md += ["\n## Most common confusions (crop-conditioned)", "| True | Predicted | Count |", "|---|---|---:|"]
md += [f"| {x['truth']} | {x['predicted']} | {x['count']} |" for x in C["top_confusions"]]
(out_dir / "plantdoc_eval.md").write_text("\n".join(md) + "\n", encoding="utf-8")
print("\n".join(md[:12]))
