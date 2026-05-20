# CineScope — Local Development Guide

Open **five terminals** and run each service in order. All must be running for the full feature set.

---

## Prerequisites

| Tool | Version |
|---|---|
| Node.js | 18+ |
| Python | 3.11+ (`py` launcher on Windows) |
| MongoDB | Atlas URI in `.env` |
| TMDB API Key | In `.env` |

Copy and populate the root `.env.example` before starting:
```powershell
cp .env.example .env   # then fill in MONGO_URI, TMDB_API_KEY, JWT_SECRET
```

---

## 1. Recommendation Service — Port 5001

```powershell
cd services/recommendation-service
npm install
npm run seed       # run once to seed genre data
npm run dev
```

Health: http://localhost:5001/health

---

## 2. ML Recommendation Engine — Port 8000

```powershell
cd services/ml-service
py -m pip install -r requirements.txt
py -m uvicorn app:app --port 8000
```

Health: http://localhost:8000/health  
*Model initialisation runs in background on first start (~30s for 800+ movies).*

---

## 3. AI Orchestration Layer — Port 9000

```powershell
cd services/ai-orchestration
py -m pip install -r requirements.txt
py -m uvicorn app:app --port 9000
```

Health: http://localhost:9000/health  
Query endpoint: `POST http://localhost:9000/api/query`  
Debug classify: `POST http://localhost:9000/debug/classify`

---

## 4. API Gateway — Port 5000

```powershell
cd backend
npm install
npm run dev
```

Health: http://localhost:5000/api/health

---

## 5. Frontend — Port 5173

```powershell
cd frontend
npm install
npm run dev
```

Open: **http://localhost:5173**

---

## Docker Compose (all services at once)

```powershell
cp .env.example .env   # fill in secrets
docker compose up --build
```

Frontend → http://localhost:80

---

## Environment Variables

| Variable | Required | Used by | Description |
|---|---|---|---|
| `MONGO_URI` | ✅ | backend, recommendation-service, ml-service | MongoDB Atlas connection string |
| `TMDB_API_KEY` | ✅ | backend, ml-service, ai-orchestration | TMDB v3 API key |
| `JWT_SECRET` | ✅ | backend | JWT signing secret |
| `OTP_SECRET` | ✅ | backend | OTP hash secret |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASS` | optional | backend | Email delivery for OTP |
| `AI_ORCHESTRATION_URL` | optional | backend | Defaults to http://localhost:9000 |
| `ML_SERVICE_URL` | optional | backend, ai-orchestration | Defaults to http://localhost:8000 |
| `RECOMMENDATION_SERVICE_URL` | optional | backend, ai-orchestration | Defaults to http://localhost:5001 |
| `REDIS_URL` | optional | ai-orchestration | L2 cache; falls back to in-memory |
