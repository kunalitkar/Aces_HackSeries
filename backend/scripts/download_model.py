"""Download the EfficientNetV2-S ONNX weights and class list from Hugging Face into models/ and verify SHA-256.

The weights are not stored in git (too large). Usage (from backend/):  .venv\\Scripts\\python scripts\\download_model.py
Set AGRISENTRY_MODEL_DIR to download somewhere else (same variable the backend reads).
"""
import hashlib
import os
import sys
import urllib.request
from pathlib import Path

REPO = "https://huggingface.co/BiernyVR/crop-disease-classifier/resolve/main/"
MODELS = Path(os.getenv("AGRISENTRY_MODEL_DIR", "").strip() or Path(__file__).resolve().parents[2] / "models")
FILES = {  # SHA-256 verified against Hugging Face (LFS oids for the weights) on 2026-10-11
    "efficientnet_v2_s_best.onnx": "14c03ae2b47b23a90a0176e70fe2fc46077fc5ae26dc46813966abdee0eb0c0a",
    "efficientnet_v2_s_best.onnx.data": "038e6093bb41434def59a3c2375fbfc13c86f6af046e7f0a5b7b9015aa29b497",
    "classes.json": "f5029dee4c360e3c4e0583c9734b6b6c68cf2177e1c1504e91030aa59f58a652",  # identical JSON to the repo's models/classes.json
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    MODELS.mkdir(parents=True, exist_ok=True)
    ok = True
    for name, expected in FILES.items():
        dest = MODELS / name
        if dest.exists() and sha256(dest) == expected:
            print(f"ok       {name} (already present, hash verified)")
            continue
        print(f"download {name} ...")
        tmp = dest.with_suffix(dest.suffix + ".part")
        req = urllib.request.Request(REPO + name, headers={"User-Agent": "agrisentry"})
        with urllib.request.urlopen(req, timeout=60) as r, tmp.open("wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        if sha256(tmp) != expected:
            tmp.unlink()
            print(f"FAILED   {name}: SHA-256 mismatch, file discarded")
            ok = False
            continue
        tmp.replace(dest)
        print(f"ok       {name} (downloaded, hash verified)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
