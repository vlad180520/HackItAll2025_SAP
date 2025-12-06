# How to Run the HackItAll2025 Project

This guide explains how to run all components of the project.

## Prerequisites

- **Python 3.10+** with pip
- **Node.js 18+** with npm
- **Java 17+** (for evaluation platform, optional)
- **Maven** (for evaluation platform, optional)

## Project Structure

```
HackItAll2025_SAP/
├── backend/          # Python FastAPI backend
├── frontend/         # React + Vite frontend
└── HackitAll2025-main/  # Java evaluation platform (external)
```

## Step 1: Setup Backend (Python FastAPI)

### 1.1 Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 1.2 Configure Environment (Optional)

Create a `.env` file in the `backend/` directory:

```bash
cd backend
cat > .env << EOF
API_BASE_URL=http://localhost:8080
API_KEY_HEADER=API-KEY
SAFETY_BUFFER=0
REORDER_THRESHOLD=10
TARGET_STOCK_LEVEL=50
LOOKAHEAD_HOURS=24
LOG_LEVEL=INFO
LOG_FILE=simulation.log
EOF
```

### 1.3 Run Tests (Optional)

```bash
cd backend
pytest tests/ -v
```

### 1.4 Start Backend Server

**From project root (Recommended):**
```bash
# Make sure you're in the project root (HackItAll2025_SAP/)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Alternative - From backend directory:**
```bash
cd backend
# Add parent directory to PYTHONPATH
PYTHONPATH=.. uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend will be available at: `http://localhost:8000`

You can verify it's running by visiting: `http://localhost:8000/`

## Step 2: Setup Frontend (React + Vite)

### 2.1 Install Dependencies

```bash
cd frontend
npm install
```

### 2.2 Start Development Server

```bash
cd frontend
npm run dev
```

The frontend will be available at: `http://localhost:5173`

The Vite dev server automatically proxies `/api/*` requests to `http://localhost:8000`

## Step 3: Setup Evaluation Platform (Java Spring Boot) - Optional

The evaluation platform is the external Java service that the backend communicates with.

### 3.1 Navigate to Evaluation Platform

```bash
cd HackitAll2025-main/eval-platform
```

### 3.2 Build with Maven

```bash
mvn clean install
```

### 3.3 Run the Platform

**Important:** The platform must be run with the `local` profile to load teams data:

```bash
mvn spring-boot:run -Dspring-boot.run.arguments=--spring.profiles.active=local
```

Or set the profile as an environment variable:
```bash
export SPRING_PROFILES_ACTIVE=local
mvn spring-boot:run
```

**Why?** The Liquibase changesets that load teams, airports, aircraft, and flights data have `context="local"`, so they only run when the `local` profile is active.

The evaluation platform will be available at: `http://localhost:8080`

**Note:** The backend expects this to be running at `http://localhost:8080` by default.

## Step 4: Run the Complete System

### Option A: Run Everything (Recommended)

**Terminal 1 - Evaluation Platform:**
```bash
cd HackitAll2025-main/eval-platform
mvn spring-boot:run
```

**Terminal 2 - Backend:**
```bash
# From project root
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 3 - Frontend:**
```bash
cd frontend
npm run dev
```

### Option B: Run Backend + Frontend Only

If you just want to test the frontend/backend integration without the evaluation platform:

**Terminal 1 - Backend:**
```bash
# From project root
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

## Step 5: Access the Application

1. Open your browser and go to: `http://localhost:5173`
2. Enter your API key in the input field (e.g., `4d344451-01c0-49ac-91ea-d2ebef71ee0f`)
3. Click "Start Simulation" to begin

## API Endpoints

Once the backend is running, you can access:

- **Root**: `http://localhost:8000/` - API status
- **Status**: `http://localhost:8000/api/status` - Simulation status
- **Inventory**: `http://localhost:8000/api/inventory` - Current inventories
- **History**: `http://localhost:8000/api/history` - Decision history
- **Start**: `POST http://localhost:8000/api/start` - Start simulation
- **Logs**: `http://localhost:8000/api/logs` - Simulation logs

## Troubleshooting

### Backend Issues

**Port 8000 already in use:**
```bash
# Find and kill the process
lsof -ti:8000 | xargs kill -9

# Or use a different port
uvicorn backend.main:app --reload --port 8001
```

**Import errors (relative import error):**
```bash
# Make sure you're running from project root, not backend directory
# Use: uvicorn backend.main:app --reload
# NOT: uvicorn main:app --reload

# If you get "ModuleNotFoundError", install dependencies:
cd backend
pip install -r requirements.txt
```

### Frontend Issues

**Port 5173 already in use:**
```bash
# Vite will automatically use the next available port
# Or specify a different port in vite.config.ts
```

**Module not found:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Evaluation Platform Issues

**Port 8080 already in use:**
```bash
# Find and kill the process
lsof -ti:8080 | xargs kill -9
```

**Maven not found:**
```bash
# Install Maven or use your IDE to run the Spring Boot application
```

## Quick Start Scripts

### Start Backend (bash)
```bash
#!/bin/bash
# Run from project root
source venv/bin/activate  # if using virtual environment
uvicorn backend.main:app --reload
```

### Start Frontend (bash)
```bash
#!/bin/bash
cd frontend
npm run dev
```

## Production Build

### Build Frontend for Production

```bash
cd frontend
npm run build
```

The production build will be in `frontend/dist/` directory.

### Serve Production Build

```bash
cd frontend
npm run preview
```

## CSV Data Files

The backend expects CSV files at:
- `eval-platform/src/main/resources/liquibase/data/airports_with_stocks.csv`
- `eval-platform/src/main/resources/liquibase/data/aircraft_types.csv`
- `eval-platform/src/main/resources/liquibase/data/flight_plan.csv`

These are located in the `HackitAll2025-main/eval-platform/` directory.

## Environment Variables

Backend configuration can be set via environment variables or `.env` file:

- `API_BASE_URL`: Base URL of evaluation platform (default: `http://localhost:8080`)
- `API_KEY_HEADER`: Header name for API key (default: `API-KEY`)
- `SAFETY_BUFFER`: Optimizer safety buffer (default: `0`)
- `REORDER_THRESHOLD`: Inventory reorder threshold (default: `10`)
- `TARGET_STOCK_LEVEL`: Target stock level (default: `50`)
- `LOOKAHEAD_HOURS`: Lookahead hours for planning (default: `24`)
- `LOG_LEVEL`: Logging level (default: `INFO`)

## Next Steps

1. **Start the evaluation platform** (if you need to run actual simulations)
2. **Start the backend** (FastAPI server)
3. **Start the frontend** (React dev server)
4. **Open the browser** and navigate to `http://localhost:5173`
5. **Enter your API key** and click "Start Simulation"

For more details, see:
- `README_BACKEND.md` - Backend architecture and details
- `README_FRONTEND.md` - Frontend architecture and details
- `ASSUMPTIONS.md` - Assumptions and defaults

