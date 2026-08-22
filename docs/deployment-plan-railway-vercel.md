# Deployment Plan: Railway Backend + Vercel Frontend

This runbook deploys:

- FastAPI backend to Railway
- Next.js frontend to Vercel

It is tailored to this repository layout:

- backend code in `src/`
- frontend app in `frontend/`

## 1. Pre-Deployment Checklist

1. Ensure the backend starts locally:
   - `uvicorn src.main:app --host 0.0.0.0 --port 8000`
2. Ensure frontend builds locally:
   - `cd frontend && npm run build`
3. Ensure tests pass:
   - `pytest`
4. Confirm secrets are not committed:
   - no real API keys in `.env.example`

## 2. Deploy Backend to Railway

### 2.1 Create Railway Service

1. In Railway, create a new project.
2. Add a service from GitHub repo.
3. Select this repository root as the service source.

### 2.2 Configure Build and Start Commands

Use these settings in Railway service configuration:

- Build Command:
  - `pip install -r requirements.txt`
- Start Command:
  - `uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}`

These are committed in-repo so Railway can auto-pick them during deploy:

- `railway.toml` (primary)
- `Procfile` (fallback)
- `runtime.txt` (Python version pin)

Optional but recommended environment setting:

- `PYTHONUNBUFFERED=1`

If Railway build logs show a `mise` Python attestation failure, this repo includes `mise.toml` with:

- `python.github_attestations = false`

so attestation verification is disabled during Python runtime install.

### 2.3 Set Railway Environment Variables

Set at minimum:

- `LLM_PROVIDER=mock` for first deploy (safe smoke test)
- `LLM_MODEL=llama-3.3-70b-versatile`
- `MAX_CANDIDATES=20`
- `MAX_RECOMMENDATIONS=5`
- `LLM_TIMEOUT_SECONDS=3.5`
- `CACHE_DIR=data/cache`
- `HF_DATASET_ID=ManikaSaini/zomato-restaurant-recommendation`
- `LOG_LEVEL=INFO`

If using Groq in production:

- `LLM_PROVIDER=groq`
- `GROQ_API_KEY=<your_real_key>`

If using Ollama, deploy separately because Railway containers do not include a local Ollama runtime by default.

### 2.4 Backend Health Validation

After deploy, verify:

1. `GET /health` returns status `ok` and `dataset_loaded=true`
2. `GET /api/v1/meta/cities` returns non-empty list
3. `POST /api/v1/recommendations` returns valid response JSON

Use Railway logs to confirm first-start dataset load completion.

## 3. Deploy Frontend to Vercel

### 3.1 Create Vercel Project

1. Import the same GitHub repository in Vercel.
2. Set project Root Directory to `frontend`.
3. Framework preset should auto-detect as Next.js.

### 3.2 Configure Vercel Environment Variables

Set this variable in Vercel (Production + Preview):

- `API_BASE_URL=https://<your-railway-backend-domain>`

You can copy defaults from `frontend/.env.example`.

Notes:

- Frontend uses Next.js rewrites from `/backend/*` to `API_BASE_URL`.
- This avoids browser-side CORS issues because calls are proxied server-side by Vercel.
- `NEXT_PUBLIC_API_BASE_URL` is optional and should only be set if you want direct browser calls.

### 3.3 Build and Output Settings

Default Vercel settings are fine for this app:

- Build Command: `npm run build`
- Install Command: `npm install`
- Output: Next.js managed output

These settings are also committed in `frontend/vercel.json`.

## 4. End-to-End Verification

After both deployments are live:

1. Open Vercel URL.
2. Confirm city dropdown is populated.
3. Fetch recommendations for at least 3 combinations:
   - location only
   - location + cuisine
   - location + budget + min rating
4. Confirm no duplicate restaurant cards.
5. Confirm graceful handling of empty result set and API errors.

## 5. Performance and Reliability Notes

1. First backend startup can be slow because dataset download and preprocessing happen at boot.
2. Railway ephemeral filesystem means cache may not persist across rebuilds/restarts.
3. For better cold start behavior, consider moving dataset to persistent object storage or shipping a preprocessed artifact.

## 6. Rollback Plan

1. Railway:
   - Redeploy previous successful deployment from Railway history.
2. Vercel:
   - Promote previous stable deployment to Production.
3. If backend contract changed, rollback frontend and backend together.

## 7. Suggested Post-Deploy Improvements

1. Add a backend `Dockerfile` for deterministic Railway builds.
2. Add CI pipeline:
   - run backend tests
   - run frontend tests
   - run frontend build
3. Add uptime checks for:
   - `/health`
   - `/api/v1/meta/cities`
4. Remove `streamlit` dependency from `requirements.txt` if no longer used.
