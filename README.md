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
| `GROQ_API_KEY`, `GROQ_MODEL` | Optional. Enables the **Ask AgriSentry** chat (Groq). Without the key the page explains how to set it up and everything else works. `GROQ_MODEL` defaults to `openai/gpt-oss-120b`; set it if Groq retires that model. |
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
| Photo quality gate | Before inference: decode/format/size checks, sharpness (Laplacian variance at 512 px), brightness, washed-out fraction, low resolution. A clear fail blocks inference unless the farmer chooses "Analyse anyway", and that result is then marked uncertain. Thresholds are calibrated on PlantDoc photos plus blurred/darkened copies (`scripts/calibrate_quality.py`) and can be overridden with `AGRISENTRY_QC_*` env vars. | Heuristic: cannot confirm a leaf is present |
| Several leaves / whole plant | Accepted; the whole photo is classified. The farmer can **mark one leaf** (drag a box) to analyse only that area; the original photo is kept. No automatic leaf detection exists. | — |
| Day-by-day risk | For each forecast day, the highest 12 h window score starting that day, its main factor and a short action. Partial days are flagged and days without scored windows are omitted. | Experimental |
| Ask AgriSentry chat | Groq LLM writes answers **only from the server-recomputed assessment** (weather risk + factors, day-by-day, photo result, advisory catalogue). Prompt forbids chemicals/doses/spray timing and diagnosis claims; a best-effort output filter replaces any reply containing a dose pattern or a listed chemical name. Sends only the question, the last 8 messages and a coordinate-free summary (no photo, no keys). A different farm/crop/source starts a new conversation. | Experimental; LLM answers can still be wrong |
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
- **Backend → a Docker host** (e.g. Render). `backend/Dockerfile` builds from **either** the repo root or the `backend/` folder (it detects which). Easiest: New → Blueprint on the repo (reads `render.yaml`); or a manual Docker service with Root Directory empty and Dockerfile Path `./backend/Dockerfile`, or Root Directory `backend` and Dockerfile Path `./Dockerfile`. The model files (~80 MB) are downloaded and hash-checked at build time; the server used ~200 MB RAM with the model loaded, so Render's 512 MB free tier should fit. Set `OPENWEATHER_API_KEY`, optionally `GROQ_API_KEY`/`GROQ_MODEL`/`DATABASE_URL`, and `CORS_ORIGINS`. Verify with `/api/health`. Don't use Vercel serverless for the backend.
- **MySQL:** any managed MySQL 8. Set `DATABASE_URL`.
- Browser location access requires HTTPS in production (localhost is exempt).
