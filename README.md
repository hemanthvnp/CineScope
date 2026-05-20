# CineScope

Movie recommendation platform built by a 3-person team. This repo covers the ML recommendation engine, the AI orchestration layer, and the backend API — my contribution to the project.

**Live:** https://cinescope-frontend-2i07.onrender.com

---

## The system at a glance

Five services. The frontend only talks to one of them.

```
React SPA
    │
    ▼
API Gateway  :5000  ──── auth, movie search, ratings
    │
    ├── ML Service        :8000  ── TF-IDF + SVD recommendations
    ├── Rec Service       :5001  ── genre-based fallback
    └── AI Orchestration  :9000  ── POST /api/query
    
All backed by MongoDB Atlas + TMDB API
```

When the ML service is initializing or down, the gateway automatically falls back to the genre-based Node service. If that's also unavailable, it falls back to TMDB trending. The frontend doesn't see any of this.

---

## How recommendations work

The recommender picks a strategy based on how many ratings the user has:

- **No ratings yet** → return trending movies
- **1–2 ratings** → content similarity only (TF-IDF cosine distance)
- **3+ ratings** → hybrid: 75% content, 25% collaborative filtering

The 75/25 split isn't arbitrary. With sparse ratings, collaborative filtering is too noisy to trust heavily. Once a user has more data, you'd tune this — it's a configurable env var.

### Content-based side

TF-IDF runs on a concatenated string: `title + overview + genre_name × 4`. The genre repetition is intentional — it inflates genre weight in the term frequency without touching the algorithm. Ten positive seeds max, negative feedback gets a 1.5× penalty on similarity scores.

### Collaborative side

Standard matrix factorization. All user-movie ratings go into a scipy CSR matrix, TruncatedSVD decomposes it into 20 latent factors, and we reconstruct the full predicted rating matrix. Fast enough to rebuild on every new rating without caching.

### Re-ranking

After scoring, candidates get bucketed by how many of the user's stated preferences they satisfy (language ∩ genre ∩ era). All three match beats two beats one, regardless of similarity score. Within a tier, a quality formula breaks ties:

```
quality = 0.60 × (vote_avg / 10)
        + 0.25 × min(vote_count / 500, 1.0)
        + 0.15 × min(popularity / 200, 1.0)
```

Non-English films use a relaxed vote_count floor (30 instead of 80). The standard threshold was filtering out most of the Indian and Korean cinema catalog — valid movies from smaller markets genuinely have fewer TMDB votes.

### Offline evaluation

`POST /metrics` on the ML service runs leave-one-out evaluation. For each user with ≥ 5 ratings, hold out their highest-rated film, run the recommender without it, check if it appears in top K. Reports Hit Rate@K, Precision@K, Recall@K, MRR, and NDCG@K.

---

## The natural-language query endpoint

`POST /api/query` takes plain text and figures out what to do with it.

```json
{
  "q": "Dark psychological thrillers like Se7en streamable in India",
  "locale": "IN",
  "options": { "max_results": 10, "include_providers": true }
}
```

The pipeline:

1. **Intent classification** — keyword/entity matching across 8 intent types (discover, find_similar, recommend, search, filter_provider, summarize, mood_based, lookup). Extracts seed movies, genres, country, year range, streaming platforms.

2. **Tool planning** — maps the intent to a set of service calls. Independent calls run in parallel via `asyncio.gather()`, dependent ones chain.

3. **Execution** — each tool call goes through a circuit breaker (CLOSED/OPEN/HALF_OPEN). If a service is failing repeatedly, it gets skipped. Results get cached at the tool level.

4. **Aggregation** — all candidates pool together, get re-scored, providers get fetched for the top N in parallel, final results returned.

Intent classification is rule-based (no LLM). It's fast, free, and deterministic — good enough for a defined set of intents. SBERT embeddings (`all-MiniLM-L6-v2`) power the semantic search component, with a TF-IDF fallback when memory is tight.

---

## Tests

```bash
pytest services/ml-service/tests/ -v
# 71 tests, ~1.6s
```

Three files:
- `test_evaluator_metrics.py` — Hit Rate, Precision, Recall, MRR, NDCG functions
- `test_hybrid_scoring.py` — quality score, quality floor, era parsing, strategy selection
- `test_intent_classifier.py` — all 8 intent types, entity extraction, country detection

The test job runs in CI before Docker build. Build won't trigger if tests fail.

---

## Running locally

You need Node 18+, Python 3.11+, a MongoDB Atlas URI, and a TMDB API key.

```bash
cp .env.example .env   # fill in MONGO_URI, TMDB_API_KEY, JWT_SECRET, OTP_SECRET
```

Five terminals:

```bash
# Recommendation service (port 5001) — run seed once on first setup
cd services/recommendation-service && npm install && npm run seed && npm run dev

# ML service (port 8000) — model init runs in background, takes ~30s
cd services/ml-service && pip install -r requirements.txt
uvicorn app:app --port 8000

# AI orchestration (port 9000)
cd services/ai-orchestration && pip install -r requirements.txt
uvicorn app:app --port 9000

# API gateway (port 5000)
cd backend && npm install && npm run dev

# Frontend (port 5173)
cd frontend && npm install && npm run dev
```

Or just: `docker compose up --build`

---

## Project layout

```
CineScope/
├── backend/                  # API gateway — auth, movie routes, service proxying
├── frontend/                 # React SPA (Vite)
├── services/
│   ├── ml-service/
│   │   ├── recommender/
│   │   │   ├── hybrid.py         # strategy selection, fusion, re-ranking
│   │   │   ├── content_based.py  # TF-IDF + cosine similarity
│   │   │   ├── collaborative.py  # TruncatedSVD matrix factorization
│   │   │   ├── evaluator.py      # leave-one-out offline evaluation
│   │   │   └── explainer.py      # "Because you liked X" explanation generation
│   │   └── clustering/           # K-Means + DBSCAN movie clustering (standalone)
│   ├── ai-orchestration/
│   │   ├── orchestrator/
│   │   │   ├── intent_classifier.py  # keyword/entity-based intent routing
│   │   │   ├── tool_planner.py       # intent → execution DAG
│   │   │   ├── execution_engine.py   # asyncio parallel executor
│   │   │   └── circuit_breaker.py    # per-service fault isolation
│   │   └── tools/                    # TMDB, ML service, semantic search, providers
│   └── recommendation-service/       # Genre-based fallback (Node.js)
├── docker-compose.yml
├── render.yaml               # Render.com deployment config
└── .github/workflows/ci-cd.yml  # test → build → push GHCR → deploy Render
```

---

## Stack

| | |
|---|---|
| Frontend | React 18, Vite, React Router |
| Gateway | Node.js, Express, JWT, bcrypt, Nodemailer |
| ML service | Python 3.11, FastAPI, scikit-learn, NumPy, SciPy, PyMongo |
| AI orchestration | Python 3.11, FastAPI, asyncio, sentence-transformers |
| Database | MongoDB Atlas |
| Movie data | TMDB REST API |
| Containers | Docker, Docker Compose |
| CI/CD | GitHub Actions → GHCR → Render.com |

---

*3-person team project. My teammates built the React frontend and the Express auth layer.*
