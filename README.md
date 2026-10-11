# AgriSentry

**See the risk. Act before it spreads.** — an AI-assisted micro-climatic crop-disease early-warning prototype for Indian farmers.

- **Leaf-image screening:** EfficientNetV2-S (ONNX, 38 PlantVillage classes, 14 crops), crop-conditioned on the crop the farmer selects.
- **Weather early warning:** live OpenWeatherMap current conditions plus a 5-day / 3-hour forecast, feeding an experimental late-blight favourability index (tomato and potato only).
- **Field advisories, alerts, history and printable reports:** stored in MySQL, or in labelled in-memory demo mode.

> Decision support only. Weather favourability does not confirm infection. Image scores are not calibrated probabilities. Visual severity is not estimated.

## Quick start (Windows / PowerShell)

```powershell
# Backend
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python scripts\download_model.py      # ONNX weights from Hugging Face, SHA-256 verified
Copy-Item .env.example .env                            # then put your OpenWeatherMap key in .env
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev                                            # http://localhost:5173 (proxies /api to :8000)
```

### Configuration (`backend/.env`, git-ignored)

| Variable | Purpose |
|---|---|
| `OPENWEATHER_API_KEY` | Enables live weather and place search. Without it, Live mode shows "unavailable" and the demo scenarios still work. |
| `DATABASE_URL` | e.g. `mysql+pymysql://agrisentry:<password>@localhost:3306/agrisentry`. The database and tables are created automatically, and columns are only ever added. Empty means in-memory demo storage (lost on restart). |
| `CORS_ORIGINS` | Comma-separated frontend origins for production (e.g. `https://<app>.vercel.app`). |
| `AGRISENTRY_MODEL_DIR`, `AGRISENTRY_UPLOAD_DIR` | Optional path overrides. Uploaded photos are stored as files; the database keeps references only. |

Frontend (`frontend/.env`): `VITE_API_URL` is the public backend URL in production. Never put secrets in `VITE_` variables.

## Tests

```powershell
cd backend;  .\.venv\Scripts\python -m pytest -q        # unit + API tests (OpenWeatherMap calls are mocked)
cd frontend; npm test; npm run build                   # component tests + type-check/build
cd frontend; node e2e/run.mjs                          # real-browser E2E in headless Edge (needs both servers running)
cd backend;  .\.venv\Scripts\python scripts\eval_plantdoc.py   # PlantDoc external evaluation -> data/eval/
```

## How it works

| Part | Method | Status |
|---|---|---|
| Image model | Model-card preprocessing (RGB, bilinear 224², ImageNet normalisation), softmax. When a crop is selected, scores are renormalised over that crop's classes. A photo is flagged uncertain if under 50% of the full score belongs to that crop, or the top score is under 50%. Single-class crops (blueberry, orange, raspberry, soybean, squash) are never renormalised. | Weights verified against Hugging Face SHA-256 |
| Late-blight index | 0–100 = favourable-run duration (50) + temperature suitability (20) + humidity (20) + rain (10) over a 12 h forward window. A favourable interval is 10–27 °C plus a leaf-wetness proxy (RH ≥ 90 %, or rain with RH ≥ 80 %). It is Smith-period-inspired. Missing values are skipped, never zero-filled, and stale observations are flagged. | **Experimental**, tomato and potato only |
| Other crops | Image screening only. No weather prediction is made. | — |
| Severity | Not estimated (no validated lesion-measurement method). Manual guidance is shown instead. | Unavailable |
| Alerts | Raised at High or above, now or forecast within 48 h. No repeat for unchanged conditions within 24 h; a rise in category always alerts. Live and simulated alerts are tracked separately. Acknowledgeable. | — |

## PlantDoc external evaluation (field photos, test split)

| Mode | Images | Accuracy |
|---|---:|---:|
| Unrestricted (all 38 classes) | 236 | 20.3 % |
| Crop-conditioned (crops with ≥ 2 classes) | 204 | 39.2 % |

The model is near-perfect on PlantVillage lab images but generalises poorly to field photos. Full per-class results are in `data/eval/plantdoc_eval.md`. These are small samples, so treat them as indicative, not a benchmark.

## Deployment

- **Frontend → Vercel:** set the project root to `frontend/` (`vercel.json` included) and set `VITE_API_URL`.
- **Backend → a Docker host** (e.g. Render via `render.yaml`): `docker build -f backend/Dockerfile .`. The model weights (~80 MB) are downloaded and hash-checked at build time. Don't use Vercel serverless for the backend.
- **MySQL:** any managed MySQL 8. Set `DATABASE_URL`.
- Browser location access requires HTTPS in production (localhost is exempt).
