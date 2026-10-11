# AgriSentry — Handoff (state after Phase 2/3, 2026-10-11)

See `README.md` for setup, configuration and the method summary. This file records **verified state, evidence and open items**.

## Architecture
```
backend/app/
  main.py      FastAPI routes (lifespan startup: db.init, model.load)
  config.py    env config (backend/.env via python-dotenv; blank values = default)
  model.py     ONNX session (once), preprocessing per model card, crop-conditioned interpretation, class catalogue
  risk.py      late-blight favourability engine + RULES export + applicability (tomato/potato only)
  weather.py   OpenWeatherMap current + 5-day forecast + geocoding; 5-min success cache; demo scenarios
  advisory.py  evidence-based advisory builder; severity explicitly unavailable
  catalog.py   per-class symptoms/prevention for all 26 disease classes (no pesticide names/doses)
  db.py        SQLAlchemy: farms, weather_observations, risk_assessments (legacy), image_predictions,
               assessments, alerts; MySQL or in-memory SQLite; additive-only migration
backend/scripts/  download_model.py · fetch_plantdoc_samples.py · eval_plantdoc.py
frontend/src/     App.tsx · useAgri.ts (state; selection = farm | ad-hoc location) · pages.tsx · LocationControls.tsx
                  ui.tsx · report.ts · api.ts · *.test.tsx · test/fixtures.ts
frontend/e2e/run.mjs  real-browser E2E (playwright-core + installed Microsoft Edge)
data/             plantdoc_samples/ (PlantDoc TEST split, 27 classes) · eval/ · e2e/ screenshots · uploads/ (git-ignored)
```

## API
`GET /api/health` · `GET/POST /api/v1/farms` · `DELETE /api/v1/farms/{id}` (user farms only) · `GET /api/v1/geocode?q=` ·
`GET /api/v1/model/classes` · `GET /api/v1/weather` · `POST /api/v1/risk/forecast` (farm_id **or** location{lat,lon}, crop, mode, image, record, refresh) ·
`POST /api/v1/diagnose-image` (file, crop, farm_id) · `GET /api/v1/advisories` · `GET /api/v1/risk/history` · `GET /api/v1/alerts` · `POST /api/v1/alerts/{id}/acknowledge`

## Verified (evidence)
| Area | Evidence |
|---|---|
| Model assets | ONNX + `.onnx.data` SHA-256 match Hugging Face LFS oids; `classes.json` identical JSON; model-card `sample_leaf.jpg` → Apple___Apple_scab (0.90) |
| Preprocessing | identical to model card (RGB, bilinear 224, /255, ImageNet mean/std, CHW); EXIF rotation added for phone photos |
| Earlier "model unavailable" | caused by a blank `AGRISENTRY_MODEL_DIR=` in `.env`; fixed (blank = default) + regression test |
| PlantDoc evaluation | 236 images / 27 classes: unrestricted 20.3 %, crop-conditioned 39.2 % (204 images, multi-class crops). Report: `data/eval/plantdoc_eval.md` |
| Live OpenWeatherMap | real calls succeed with the configured key (Nashik/Kolar current + 41-point forecast), exercised in E2E |
| Backend tests | 43/43 pytest (OWM responses mocked in tests) |
| Frontend tests | 14/14 vitest (geolocation consent/granted/denied/timeout/unsupported, crop catalogue, farm switch, alerts, report) + `npm run build` |
| Real-browser E2E | headless Edge against the real backend, live weather and real ONNX: no geolocation request on load; granted permission → current-location weather, nothing saved; denied → message + manual selection intact; real inference on a PlantDoc late-blight photo (98 %); 14 crops listed; scenario switch; save → history; alert acknowledge; desktop menu hidden; 390 px mobile no horizontal scroll on 5 views; no console errors |
| MySQL persistence | Local MySQL 8.0.44 via `DATABASE_URL` in `backend/.env`: tables auto-created (6); assessment + alert saved, backend restarted, both read back; full E2E 18/18 against MySQL |
| Persistence logic | SQLite file DB persists across re-init; additive migration of an MVP-era `alerts` table keeps data; bad URL falls back to labelled memory |

## NOT verified / blocked
- **Docker image**: `backend/Dockerfile` written but not built (Docker not installed here).
- **Deployment**: nothing deployed; no Vercel/Render/managed-MySQL accounts available in this session. No production URLs exist.
- Live-weather unit tests use mocked payloads; the live path is verified only via the E2E run.

## Known limitations
- Image model generalises poorly to field photos (tomato healthy 0/8, mosaic 0/10, leaf mold 0/6 even crop-conditioned).
- Late-blight index thresholds are heuristics (Smith-period-inspired), unvalidated: needs agronomist review/local validation.
- Free OWM plan gives 3-hour steps; favourable-run length is step-approximated.
- Uploaded photos are stored on local disk (`data/uploads`); on ephemeral hosts use a persistent disk or object storage.
- No authentication; single demo user. Seed farms cannot be deleted.

## Deliberately not done
Fine-tuning (see next actions), severity estimation (no defensible validated method), SMS/WhatsApp, auth.

## Highest-value next actions
1. **Fine-tune on the PlantDoc *train* split** (test split held out, already used for evaluation): needs PyTorch and the `.pth` checkpoint from the HF repo; the evaluation shows a large field-photo gap. Re-run `eval_plantdoc.py` before/after; keep crop-conditioning.
2. **Provision managed MySQL** for production (local MySQL verified) and set `DATABASE_URL` on the host.
3. **Deploy**: Docker backend (Render blueprint included), Vercel frontend with `VITE_API_URL`, set `CORS_ORIGINS`; re-run `e2e/run.mjs` with `E2E_URL` against production (geolocation needs HTTPS).
