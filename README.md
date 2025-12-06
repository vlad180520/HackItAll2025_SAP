# HackItAll2025_SAP

Airline Kit Management Optimization System

## Quick Start

### 1. Backend Setup
```bash
cd backend
pip install -r requirements.txt
cd ..
uvicorn backend.main:app --reload --port 8000
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### 3. Evaluation Platform (Optional)
```bash
cd HackitAll2025-main/eval-platform
mvn spring-boot:run
```

### 4. Access Application
Open browser: `http://localhost:5173`

## Documentation

- **[RUN.md](RUN.md)** - Complete setup and running instructions
- **[README_BACKEND.md](README_BACKEND.md)** - Backend architecture
- **[README_FRONTEND.md](README_FRONTEND.md)** - Frontend architecture
- **[ASSUMPTIONS.md](ASSUMPTIONS.md)** - Assumptions and defaults

## Project Structure

- `backend/` - Python FastAPI backend
- `frontend/` - React + Vite frontend
- `HackitAll2025-main/` - Java evaluation platform (external)