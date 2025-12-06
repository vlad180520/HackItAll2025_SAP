# Backend Setup și Rulare

## Schimbări efectuate

### 1. Imports globale în loc de relative
- Toate importurile au fost schimbate de la `from .module` la `from module`
- Nu mai e nevoie de structura de package pentru a rula codul
- Modulele pot fi importate direct

### 2. Eliminat uvicorn ca dependență separată
- Nu mai folosim `uvicorn.run()` în `main.py`
- Folosim `fastapi[standard]` care include uvicorn automat
- Rulăm cu comanda oficială FastAPI: `python -m fastapi dev main.py`

### 3. Virtual Environment (.venv) configurat corect
- Am creat un .venv funcțional
- Toate dependințele sunt actualizate pentru Python 3.13
- Requirements.txt actualizat cu versiuni compatibile

## Dependințe actualizate (requirements.txt)

```
fastapi[standard]==0.115.5  # Include uvicorn automat
pydantic==2.10.3
pydantic-settings==2.6.1
pandas==2.2.3                # Compatibil cu Python 3.13
requests==2.32.3
pytest==8.3.4
python-dotenv==1.0.1
```

## Setup

### Opțiunea 1: Folosind scriptul automat
```bash
cd backend
./setup_venv.sh
```

### Opțiunea 2: Manual
```bash
cd backend

# Creează virtual environment
python3 -m venv .venv

# Activează environment-ul
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Instalează dependencies
pip install -r requirements.txt
```

## Rulare

### Opțiunea 1: Folosind scriptul
```bash
cd backend
./run_server.sh
```

### Opțiunea 2: Manual
```bash
cd backend
source .venv/bin/activate
python -m fastapi dev main.py --port 8000
```

### Opțiunea 3: Pentru producție
```bash
cd backend
source .venv/bin/activate
python -m fastapi run main.py --port 8000
```

## Acces

- **API**: http://127.0.0.1:8000
- **Documentație interactivă**: http://127.0.0.1:8000/docs
- **API alternativă**: http://127.0.0.1:8000/redoc

## Endpoint-uri disponibile

- `GET /` - Root endpoint
- `POST /api/start` - Start simulation
- `GET /api/status` - Status simulare
- `GET /api/inventory` - Inventar
- `GET /api/history` - Istoric
- `GET /api/logs` - Logs

## Notițe

- Environment-ul se activează automat cu scripturile
- FastAPI include reload automat în modul dev
- Pentru oprire: `Ctrl+C`
- Logs apar în consolă în timp real
