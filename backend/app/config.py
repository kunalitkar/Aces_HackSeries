import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

try:  # backend/.env (git-ignored) is the supported place for secrets
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass
MODEL_DIR = Path(os.getenv("AGRISENTRY_MODEL_DIR", "").strip() or ROOT / "models")  # blank in .env = default
MODEL_PATH = MODEL_DIR / "efficientnet_v2_s_best.onnx"
CLASSES_PATH = MODEL_DIR / "classes.json"
MODEL_VERSION = "efficientnet_v2_s@BiernyVR/crop-disease-classifier (weights sha256 038e6093)"
UPLOAD_DIR = Path(os.getenv("AGRISENTRY_UPLOAD_DIR", "").strip() or ROOT / "data" / "uploads")  # image files; DB stores references only

OWM_API_KEY = os.getenv("OPENWEATHER_API_KEY", "").strip()
# e.g. mysql+pymysql://user:pass@localhost:3306/agrisentry (any SQLAlchemy URL works)
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
CORS_ORIGINS = [o.strip() for o in (os.getenv("CORS_ORIGINS", "").strip() or "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
MAX_UPLOAD_BYTES = 8 * 1024 * 1024

FARMS = [
    {"id": 1, "name": "Sahyadri Polyhouse", "location": "Nashik, Maharashtra", "lat": 19.9975, "lon": 73.7898, "crop": "Tomato"},
    {"id": 2, "name": "Junnar Hillside Plot", "location": "Junnar, Pune, Maharashtra", "lat": 19.2076, "lon": 73.8759, "crop": "Tomato"},
    {"id": 3, "name": "Kolar Tomato Farm", "location": "Kolar, Karnataka", "lat": 13.1357, "lon": 78.1292, "crop": "Tomato"},
    {"id": 4, "name": "Nilgiri Terrace Farm", "location": "Udhagamandalam, Tamil Nadu", "lat": 11.4102, "lon": 76.6950, "crop": "Tomato"},
]
