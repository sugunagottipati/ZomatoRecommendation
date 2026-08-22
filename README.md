# Zomato AI Restaurant Recommendation System

An AI-powered restaurant recommendation service inspired by Zomato. The system combines structured data filtering with an LLM to deliver personalized, explainable recommendations based on your location, budget, cuisine preference, and rating requirements.

---

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full system design, component breakdown, and request-flow diagrams.

---

## Quick Start

### Prerequisites

- Python 3.11+
- An [OpenAI](https://platform.openai.com/) or [Anthropic](https://console.anthropic.com/) API key  
  *(or [Ollama](https://ollama.ai/) running locally for offline use)*

### 1. Clone & create a virtual environment

```bash
git clone <repo-url>
cd ZomatoRecommendation

python3.11 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and set at least:
#   LLM_PROVIDER=openai
#   OPENAI_API_KEY=sk-...
```

### 4. Start the API server

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

On first startup the ~574 MB Zomato dataset is downloaded from Hugging Face and cached locally in `data/cache/`. Subsequent startups load from cache and are fast.

### 5. Start the Next.js frontend (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

If your API is not on `http://localhost:8000`, set:

```bash
NEXT_PUBLIC_API_BASE_URL=http://<api-host>:<port>
```

For Vercel deployment, set `API_BASE_URL` to your Railway backend URL (see `frontend/.env.example`). Frontend calls route through an internal `/backend/*` proxy endpoint.

---

## Configuration Reference

All settings are documented in [`.env.example`](.env.example).

| Key | Default | Description |
|-----|---------|-------------|
| `LLM_PROVIDER` | `mock` | `openai` \| `anthropic` \| `ollama` \| `mock` |
| `LLM_MODEL` | `gpt-4o-mini` | Model name for the selected provider |
| `OPENAI_API_KEY` | — | Required for OpenAI provider |
| `ANTHROPIC_API_KEY` | — | Required for Anthropic provider |
| `MAX_CANDIDATES` | `20` | Restaurants forwarded to the LLM (token budget) |
| `MAX_RECOMMENDATIONS` | `5` | Results returned to the user |
| `LLM_TIMEOUT_SECONDS` | `3.5` | Hard LLM request timeout |
| `CACHE_DIR` | `data/cache` | Local dataset cache directory |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/recommendations` | Generate personalized recommendations |
| `GET` | `/api/v1/meta/locations` | List supported cities |
| `GET` | `/api/v1/meta/cities` | List supported cities (location-field alias) |
| `GET` | `/api/v1/meta/cuisines` | List available cuisines |
| `GET` | `/health` | Service health & dataset status |

Interactive API docs available at [http://localhost:8000/docs](http://localhost:8000/docs) once the server is running.

---

## Running Tests

```bash
pytest                          # run all tests
pytest tests/unit/              # unit tests only
pytest tests/integration/       # integration tests only
pytest --cov=src --cov-report=term-missing   # with coverage
```

## Pre-Deployment Check (Phase 1)

Run the consolidated readiness checks before deploying:

```bash
./scripts/predeploy_check.sh
```

This validates:

- no obvious secrets in `.env.example`
- backend import/startup wiring
- backend test pass
- frontend production build

---

## Docker

```bash
# Build
docker build -t zomato-rec .

# Run (pass API key via env)
docker run -e OPENAI_API_KEY=sk-... -p 8000:8000 zomato-rec
```

Or use Docker Compose (API + UI together):

```bash
docker-compose up --build
```

---

## Project Structure

```
ZomatoRecommendation/
├── docs/               # Architecture, implementation plan, evaluation docs
├── src/
│   ├── config.py       # Pydantic-settings configuration
│   ├── main.py         # FastAPI app entry point  (Phase 5)
│   ├── models/         # Pydantic domain models   (Phase 2)
│   ├── data/           # Dataset loader & repo    (Phase 1)
│   ├── services/       # Business logic           (Phase 3–4)
│   ├── llm/            # LLM client & prompt eng  (Phase 4)
│   └── api/            # FastAPI routes            (Phase 5)
├── frontend/
│   ├── app/            # Next.js app router pages
│   ├── components/     # UI, filter, and result components
│   └── lib/            # API client + frontend types
├── tests/
│   ├── unit/
│   └── integration/
├── data/               # Local cache (gitignored)
├── .env.example        # Configuration template
├── requirements.txt
└── Dockerfile
```

---

## Known Limitations

- Dataset (~51K records, ~574 MB) is downloaded once on first run; requires internet access or pre-populated cache.
- MVP is stateless — no user sessions or order history persistence.
- Recommendations depend on LLM availability; a rule-based fallback activates on provider failure.

## Future Extensions

See [`docs/architecture.md §13`](docs/architecture.md#13-future-extensions) for planned enhancements including vector search, multi-turn chat, geolocation filtering, and feedback loops.
