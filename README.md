# AgriSentry

**See the risk. Act before it spreads.** — an AI-assisted crop-disease early-warning prototype for Indian farmers.

- **Leaf-photo screening:** EfficientNetV2-S (ONNX) recognises 38 crop-health classes across 14 crops. A photo-quality check runs first, and the farmer can mark one leaf in a photo with several.
- **Weather early warning:** live OpenWeatherMap conditions and a 5-day forecast feed an *experimental* late-blight risk score (tomato and potato only), with plain-language reasons and a day-by-day view.
- **Field advisories, alerts, history, printable reports** and an optional **Ask AgriSentry** chat (Groq).
- Works **without any API keys** in demo mode (clearly labelled simulated weather).

> Decision support only. Weather risk does not confirm infection. Image scores are not probabilities of infection. Visual severity is not estimated. Always confirm in the field and with your local Krishi Vigyan Kendra (KVK).

---

## 1. What you need

| Tool | Version | Check with |
|---|---|---|
| Git | any recent | `git --version` |
| Python | **3.11 or newer** (3.11 tested) | `python --version` (Windows: `py -3.11 --version`) |
| Node.js | **22.12 or newer** for running tests (20.19+ is enough to run and build) | `node -v` |
| Internet | to download the model (~80 MB) and install packages | |

**Optional:** an [OpenWeatherMap](https://openweathermap.org/api) key (free tier; new keys can take up to 2 hours to activate), a [Groq](https://console.groq.com) key for the chat, and MySQL 8 for permanent storage. Without them the app still runs.

## 2. Install and run

Open **two terminals**. Commands are shown for Windows (PowerShell) and for macOS/Linux (bash/zsh).

### 2.1 Get the code

```bash
git clone https://github.com/kunalitkar/Aces_HackSeries.git
cd Aces_HackSeries
```

### 2.2 Backend (terminal 1)

**Windows (PowerShell)**
```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python scripts\download_model.py        # downloads the model, checks SHA-256
Copy-Item .env.example .env                              # optional: add your keys, see section 3
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

**macOS / Linux**
```bash
cd backend
python3.11 -m venv .venv          # or: python3 -m venv .venv  (must be 3.11+)
./.venv/bin/python -m pip install -r requirements-dev.txt
./.venv/bin/python scripts/download_model.py
cp .env.example .env
./.venv/bin/python -m uvicorn app.main:app --port 8000
```

You do not need to "activate" the virtual environment; the commands call its Python directly. When the backend is ready you will see `Application startup complete`. Leave it running.

Check it: open <http://localhost:8000/api/health>. You should see `"model": {"available": true, ... "num_classes": 38}`.

### 2.3 Frontend (terminal 2)

```bash
cd frontend          # from the repository folder (NOT backend)
npm install
npm run dev
```

Open **<http://localhost:5173>**. The dev server forwards `/api` requests to the backend on port 8000.

### 2.4 What works with no keys

Choose **Demo: normal** or **Demo: disease-conducive** at the top to see the whole workflow with simulated weather: risk score, reasons, day-by-day view, advisories, alerts, history, reports and photo upload. Live weather, place search and the chat need their keys.

## 3. Configuration

Settings go in **`backend/.env`** (created from `.env.example`; git ignores it, so your keys are never uploaded). Restart the backend after editing. Leaving a value blank means "use the default".

| Variable | Purpose |
|---|---|
| `OPENWEATHER_API_KEY` | Live weather and place search. Without it, "Live weather" shows *unavailable* and the demo scenarios still work. |
| `GROQ_API_KEY`, `GROQ_MODEL` | Optional chat. `GROQ_MODEL` defaults to `openai/gpt-oss-120b`; set it if Groq retires that model (list yours: <https://console.groq.com/docs/models>). |
| `DATABASE_URL` | MySQL, e.g. `mysql+pymysql://agrisentry:<password>@localhost:3306/agrisentry`. Empty means temporary in-memory storage (lost on restart). |
| `CORS_ORIGINS` | Comma-separated frontend addresses allowed to call the backend (needed in production). |
| `AGRISENTRY_MODEL_DIR`, `AGRISENTRY_UPLOAD_DIR` | Optional folders for the model files and uploaded photos. |

Never put keys in the frontend. Only when deploying, copy `frontend/.env.example` to `frontend/.env` and set `VITE_API_URL` (the public backend address); local development needs no frontend settings.

### Optional: permanent storage with MySQL

Create a database and a dedicated user once (as the MySQL admin), choosing your own password:

```sql
CREATE DATABASE IF NOT EXISTS agrisentry CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'agrisentry'@'localhost' IDENTIFIED BY 'ChooseAStrongPassword';
GRANT ALL PRIVILEGES ON agrisentry.* TO 'agrisentry'@'localhost';
```

Put the matching `DATABASE_URL` in `backend/.env` and restart. The tables are created automatically (only ever added to, never dropped). `http://localhost:8000/api/health` then shows `"persistent": true`. Passwords containing `@ : / # ? %` must be URL-encoded.

## 4. Troubleshooting

| Problem | Fix |
|---|---|
| `npm error ENOENT ... package.json` | You ran npm in the wrong folder. Use `frontend/`, not `backend/`. |
| `error while attempting to bind on address ... 8000` | Another backend is already running. Close it, or use `--port 8001` and start the frontend with `VITE_PROXY_TARGET=http://127.0.0.1:8001 npm run dev` (bash) or `$env:VITE_PROXY_TARGET="http://127.0.0.1:8001"; npm run dev` (PowerShell). |
| "Image model unavailable" | Run `scripts/download_model.py` (step 2.2). Make sure `AGRISENTRY_MODEL_DIR` is empty or correct. |
| "Cannot reach the AgriSentry backend" | The backend is not running, or is not on port 8000. |
| Live weather "rejected the API key (401)" | Key mistyped, or a new key still activating (up to 2 hours). |
| Chat: "model not available (404)" | Set `GROQ_MODEL` in `backend/.env` to a model your key can use. |
| "Use my location" blocked | Browsers allow location only on `localhost` or HTTPS, and only after you allow it. |
| `python` or `py` not found | Install Python 3.11+ from python.org (Windows: tick "Add to PATH"). |
| Old Python (3.9/3.10) install errors | Use Python 3.11 or newer. |

## 5. Tests

```bash
# backend (OpenWeatherMap and Groq calls are mocked)
cd backend && ./.venv/bin/python -m pytest -q          # Windows: .\.venv\Scripts\python -m pytest -q
# frontend
cd frontend && npm test && npm run build
# real-browser end-to-end (needs both servers running and Microsoft Edge installed)
cd frontend && node e2e/run.mjs
# model evaluation on PlantDoc field photos -> data/eval/
cd backend && ./.venv/bin/python scripts/eval_plantdoc.py
```

## 6. Project layout

```
backend/app/        FastAPI app: main (routes), model (ONNX), quality (photo checks), risk (weather score),
                    weather (OpenWeatherMap), advisory + catalog (advice), chat (Groq), db (SQLAlchemy), config
backend/scripts/    download_model.py · fetch_plantdoc_samples.py · eval_plantdoc.py · calibrate_quality.py
backend/tests/      pytest suites
frontend/src/       React + Vite + TypeScript + Tailwind UI (pages, charts, tests)
frontend/e2e/       real-browser end-to-end script
models/             classes.json (model weights are downloaded by download_model.py, not stored in git)
data/               PlantDoc test photos, evaluation reports, quality calibration
render.yaml, backend/Dockerfile, frontend/vercel.json    deployment files
HANDOFF.md          current status, test evidence, known limits, next steps
```

## 7. How it works

| Part | Method | Status |
|---|---|---|
| Image model | EfficientNetV2-S ONNX; model-card preprocessing (RGB, bilinear 224², ImageNet normalisation), softmax. When a crop is chosen, scores are renormalised over that crop's classes; a photo is flagged uncertain if under 50 % of the full score belongs to that crop or the top score is under 50 %. Single-class crops (blueberry, orange, raspberry, soybean, squash) cannot separate healthy from diseased. | Weights hash-verified |
| Photo quality | Before inference: readable image, size, sharpness, brightness, washed-out light. A clear failure blocks analysis unless the farmer chooses "Analyse anyway" (then marked unreliable). Thresholds were calibrated on PlantDoc photos plus blurred/darkened copies. | Heuristic; cannot confirm a leaf is present |
| Several leaves | The whole photo is classified; the farmer can drag a box to check one leaf. There is no automatic leaf detection. | — |
| Late-blight score | 0–100 = cool-wet hours in a row (50) + temperature (20) + humidity (20) + rain (10) over 12 h. Smith-period-inspired. Missing data is skipped, never treated as zero. | **Experimental**, tomato and potato only |
| Other crops | Photo screening only; no weather score. | — |
| Ask AgriSentry | Groq writes answers only from the server's own assessment; chemicals, doses and spray schedules are forbidden and filtered. Sends no photo and no coordinates. | Experimental; can be wrong |
| Severity | Not estimated. | Unavailable |
| Alerts | At High or above (now or within 48 h); no repeat within 24 h unless the level rises. | — |

**Accuracy on real field photos (PlantDoc test split):** 20.3 % over all 38 classes (236 images) and 39.2 % when the crop is chosen (204 images). The model is near-perfect on clean lab images but weak on field photos, so treat results as screening. Details: `data/eval/plantdoc_eval.md`.

## 8. Deployment

- **Frontend → Vercel:** import the repo, set the project root to `frontend`, and set `VITE_API_URL` to the backend's HTTPS address.
- **Backend → a Docker host (e.g. Render):** `backend/Dockerfile` builds from the repository root or from `backend/`. Easiest on Render: New → Blueprint (reads `render.yaml`). The model is downloaded and verified during the build; the server used about 200 MB of RAM. Set `OPENWEATHER_API_KEY`, optionally `GROQ_API_KEY` / `DATABASE_URL`, and `CORS_ORIGINS` (your Vercel address). Check `/api/health`. Do not run the backend on Vercel serverless.
- **MySQL:** any managed MySQL 8; set `DATABASE_URL`.
- Browser location access requires HTTPS when deployed.
