# AgriSentry — Handoff (mid-evaluation MVP → final evaluation)

## Architecture
```
D:\AgriSentry
├─ models\                    efficientnet_v2_s_best.onnx (+ .onnx.data external weights), classes.json
│                             (copied from the originals in the project root; originals untouched)
├─ data\plantdoc_samples\     18 PlantDoc TEST-split tomato images: late_blight\ (10), healthy\ (8)
├─ backend\                   Python 3.11 venv at backend\.venv
│  ├─ app\main.py             FastAPI routes
│  ├─ app\risk.py             late-blight favourability engine (heuristic, documented in docstring)
│  ├─ app\weather.py          OpenWeatherMap (free /weather + /forecast, 3-hourly) + 2 simulated scenarios
│  ├─ app\model.py            ONNX Runtime CPU session (loaded once), preprocessing, softmax, label parsing
│  ├─ app\advisory.py         combines weather risk + image result into farmer advice
│  ├─ app\db.py               SQLAlchemy models (Farm, WeatherObservation, RiskAssessment, ImagePrediction, Alert)
│  ├─ tests\test_backend.py   13 pytest tests
│  └─ scripts\                fetch_plantdoc_samples.py, eval_plantdoc.py
└─ frontend\                  React 19 + Vite + TS + Tailwind v4 + Recharts + lucide
   └─ src\ App.tsx (shell), useAgri.ts (state), pages.tsx (5 views), ui.tsx (gauge/charts), api.ts, App.test.tsx
```
Image prediction, weather favourability and the combined advisory are computed separately. The image result never feeds the weather index.
No prototype (plain HTML/JS) or earlier model code was found in the workspace, so everything was built fresh.

## Run locally (verified commands)
Backend (PowerShell, from `D:\AgriSentry\backend`):
```
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000
```
Recreate the venv if needed: `py -3.11 -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`
Frontend (from `D:\AgriSentry\frontend`): `npm install` then `npm run dev` → http://localhost:5173 (Vite proxies `/api` to 127.0.0.1:8000).
Tests: `.\.venv\Scripts\python -m pytest -q` (backend), `npm test` and `npm run build` (frontend).
PlantDoc sanity eval: `.\.venv\Scripts\python scripts\eval_plantdoc.py`

## Environment variables (all optional)
| Var | Effect |
|---|---|
| `OPENWEATHER_API_KEY` | enables Live mode. Unset → Live shows "unavailable" (never silently replaced by demo data). When set, the UI defaults to Live. |
| `DATABASE_URL` | e.g. `mysql+pymysql://user:pass@localhost:3306/agrisentry`. Tables auto-created and farms seeded at startup. Unset → demo mode: history is the server session (volatile) or labelled synthetic entries. |
| `AGRISENTRY_MODEL_DIR` | override model folder (default `..\models`) |
| `CORS_ORIGINS` / frontend `VITE_API_URL` | for separate frontend/backend hosting |

## What works and how it was verified
| Item | Evidence |
|---|---|
| Model loads; input `[N,3,224,224]` float, output `logits [N,38]`; 38 classes in `classes.json` match output dim | inspected with onnxruntime; `test_label_mapping`, `/api/health` |
| Real inference, preprocessing: RGB, bilinear resize 224×224 (no crop), /255, ImageNet mean/std from `classes.json` | `test_inference_*`; ~70 ms CPU per image on this laptop |
| Upload validation (type, ≥64 px, ≤8 MB, empty, unreadable, GIF) | `test_upload_validation`; also client-side checks in UI test |
| Risk engine bounds, factor points sum exactly to index, normal=Low vs conducive=High/Very High, missing values skipped not zero-filled | `test_scenarios_*`, `test_missing_values_*` |
| Scenario switch changes weather, index, factors, trend, advisory consistently | `test_forecast_endpoint_*`, frontend test |
| Live weather failure handling (no key, network error) | `test_live_weather_*` (mocked failure; no real key used) |
| Advisory combos (high+LB, high+healthy, low+LB, non-tomato, weather/model missing) | `test_advisory_combinations` |
| DB layer | `test_database_layer_with_sqlite` — SQLAlchemy models exercised on **SQLite** |
| End-to-end through Vite proxy | curl against :5173: health, forecast (conducive → 73 High), image upload (late blight sample → Tomato___Late_blight 0.90), live-without-key → unavailable |

Results: backend **13/13 pytest passed**; frontend **3/3 vitest passed** (navigation, scenario switch, upload rejection; Recharts stubbed); `npm run build` succeeds.

### PlantDoc sanity check — important caveat
18 test-split tomato images: **5/18 exact class matches** (late blight 5/10; healthy 0/8). Failures include healthy leaves predicted as Early blight / Septoria / bell-pepper healthy, and late blight predicted as Strawberry leaf scorch or Early blight. The model is PlantVillage-style (lab) and does **not** generalise well to field photos. This is a tiny sample, not a benchmark, but the direction is clear. The UI warns about this; do not quote the model's 99.9 % val accuracy as field accuracy.

## Not tested / blocked
- **Not tested in a real browser** (no Playwright/screenshots run). Layout, responsiveness and chart rendering are only verified by a successful build and jsdom tests. Do a visual pass first.
- **Live OpenWeatherMap**: no API key available; only failure paths tested. Free plan gives 3-hourly 5-day forecast (used); hourly forecast needs a paid plan. Response parsing is untested against a real payload.
- **MySQL**: not installed here. `pymysql` is in requirements; code path tested only via SQLite.
- Production deployment (Vercel / Python host) not attempted.

## Known issues / design notes
- Risk thresholds are documented heuristics (Smith-period-inspired), not validated; need agronomist review.
- 3-hourly live data: favourable "run" length is approximated as steps × step-hours.
- `@app.on_event` is deprecated (works; migrate to lifespan). Frontend bundle is 666 kB (no code-splitting).
- Notification bell/profile menu are derived from current state only (no persistent alerts UI beyond the History page).
- Visual severity is deliberately not implemented; UI says it requires field inspection.
- Profile menu is a prototype stub (no authentication).

## Deliberately deferred
Fine-tuning / training, full PlantDoc benchmark, multi-crop support, severity estimation, SMS/WhatsApp, auth, Vercel/production DB.

## Top 3 next actions for final evaluation
1. **Fix field-photo generalisation**: evaluate on more PlantDoc tomato test images, try restricting softmax to tomato classes (only if input is known tomato), and consider fine-tuning on PlantDoc *train* split with the test split held out; keep the honest caveat until improved.
2. **Real-world verification pass**: add an OpenWeatherMap key and confirm live mode; run the app in a browser on desktop + phone width (fix any layout issues, take screenshots); configure a MySQL instance and verify persistence.
3. **Deploy and harden**: frontend to Vercel (`VITE_API_URL`), backend to a Python host that can ship the ONNX `.data` weights (set `CORS_ORIGINS`), managed MySQL; have an agronomist review the risk thresholds and advisory wording.
