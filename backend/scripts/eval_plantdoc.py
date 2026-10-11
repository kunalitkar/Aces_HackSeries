"""Tiny sanity check on PlantDoc tomato test images. NOT a reliable accuracy benchmark."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import model  # noqa: E402

root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "data" / "plantdoc_samples")
truth = {"late_blight": "Tomato___Late_blight", "healthy": "Tomato___healthy"}
rows, correct = [], 0
for folder, label in truth.items():
    for f in sorted((root / folder).glob("*")):
        try:
            r = model.classify(f.read_bytes())
        except model.ImageRejected as e:
            rows.append((folder, f.name, "REJECTED: " + str(e), 0, False)); continue
        ok = r["label"] == label
        correct += ok
        rows.append((folder, f.name, r["label"], r["score"], ok))
for fo, n, p, s, ok in rows:
    print(f"{'OK ' if ok else 'XX '} {fo:12} {n[:38]:38} -> {p} ({s:.2f})")
print(f"\n{correct}/{len(rows)} matched exact class (small sample; field photos; NOT a benchmark)")
