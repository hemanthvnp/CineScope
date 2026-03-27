# CineScope - Execution Guide

To run the full CineScope application, open four separate terminals and execute the following commands in order:

### 1. Backend API Gateway (Port 5000)
```powershell
cd backend
npm install
npm run dev
```

### 2. Recommendation Microservice (Port 5001)
```powershell
cd services/recommendation-service
npm install
npm run seed  # Run once to initialize genre data
npm run dev
```

### 3. ML Recommendation Service (Port 8000)
```powershell
cd services/ml-service
pip install -r requirements.txt
python -m uvicorn app:app --port 8000 --reload
```

### 4. Frontend Application
```powershell
cd frontend
npm install
npm run dev
```

---
**Health Check Endpoints:**
- Gateway: `http://localhost:5000/api/health`
- Rec Service: `http://localhost:5001/health`
- ML Service: `http://localhost:8000/health`
