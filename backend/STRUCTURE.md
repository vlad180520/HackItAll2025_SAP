# Backend Structure

Backend organizat și simplificat pentru optimizarea kit-urilor de airline.

## 📁 Structură Organizată

```
backend/
├── 🎯 solution/                    # LOGICA PRINCIPALĂ DE SOLUȚII
│   ├── config.py                  # Parametri configurabili
│   ├── decision_maker.py          # Orchestrator
│   ├── README.md                  # Documentație detaliată
│   └── strategies/
│       └── greedy_strategy.py     # Implementare greedy
│
├── 📊 models/                      # Modele de date
│   ├── aircraft.py
│   ├── airport.py
│   ├── flight.py
│   ├── game_state.py
│   └── kit.py
│
├── 🌐 routes/                      # API endpoints
│   ├── simulation_routes.py
│   ├── status_routes.py
│   └── logs_routes.py
│
├── 📋 schemas/                     # Request/Response schemas
│   ├── simulation_schemas.py
│   ├── status_schemas.py
│   └── logs_schemas.py
│
├── 🔧 services/                    # Business logic
│   ├── simulation_service.py
│   └── singleton.py
│
├── 🧪 tests/                       # Unit tests
│
├── 🔌 Core Files
│   ├── main.py                    # FastAPI app
│   ├── solution_optimizer.py     # Integrator cu solution/
│   ├── optimizer.py               # Optimizer original (legacy)
│   ├── api_client.py             # HTTP client extern
│   ├── state_manager.py          # Game state management
│   ├── validator.py              # Pre-submission validation
│   ├── cost_calculator.py        # Cost calculations
│   ├── data_loader.py            # CSV parsing
│   ├── config.py                 # Main config
│   └── logger.py                 # Logging setup
│
└── 📄 Configuration
    ├── requirements.txt           # Python dependencies
    ├── .env                       # Environment variables
    ├── setup_venv.sh             # Setup script
    └── run_server.sh             # Run script
```

## 🚀 Quick Start

### Setup

```bash
# Setup virtual environment
./setup_venv.sh

# Sau manual:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run Server

```bash
# Activează venv
source .venv/bin/activate

# Run cu FastAPI
python -m fastapi dev main.py --port 8000

# Sau folosește script-ul
./run_server.sh
```

## 🎯 Modifică Soluția

### 1. Parametri Rapizi
Editează `solution/config.py`:
```python
SAFETY_BUFFER = 10
TARGET_STOCK_LEVEL = 60
LOOKAHEAD_HOURS = 48
```

### 2. Logica de Purchase
Editează `solution/strategies/greedy_strategy.py`:
```python
class GreedyPurchaseStrategy:
    def decide_purchases(self, state, flights, airports):
        # MODIFICĂ AICI
        pass
```

### 3. Logica de Loading
Editează `solution/strategies/greedy_strategy.py`:
```python
class GreedyLoadingStrategy:
    def decide_loading(self, state, flights, airports, aircraft_types):
        # MODIFICĂ AICI
        pass
```

## 📚 Documentație Detaliată

- **solution/README.md** - Ghid complet pentru modificări
- **ARCHITECTURE.md** - Arhitectura sistemului

## 🔧 Development

### Structură Modulară

- **solution/** - Toată logica de optimizare (modifică aici!)
- **models/** - Data models (citește, nu modifica)
- **routes/** - API endpoints (stabil)
- **services/** - Business logic (stabil)

### Import-uri Globale

Backend-ul folosește import-uri globale (fără relative imports):
```python
from models.game_state import GameState
from solution.config import SolutionConfig
```

### Testing

```bash
source .venv/bin/activate
pytest tests/
```

## 📊 API Endpoints

- `POST /api/start` - Start simulation
- `GET /api/status` - Get current status
- `GET /api/inventory` - Get inventory
- `GET /api/history` - Get history
- `GET /api/logs` - Get logs

## 🔍 Key Files

| Fișier | Scop | Modifică? |
|--------|------|-----------|
| `solution/config.py` | Parametri | ✅ DA |
| `solution/strategies/greedy_strategy.py` | Logică principală | ✅ DA |
| `solution_optimizer.py` | Integrator | ❌ NU |
| `main.py` | FastAPI app | ❌ NU |
| `models/*.py` | Data models | ❌ NU |

## 💡 Tips

1. **Pentru modificări rapide**: Editează doar `solution/config.py`
2. **Pentru logică nouă**: Editează `solution/strategies/greedy_strategy.py`
3. **Pentru debugging**: Vezi logs în console și `simulation.log`
4. **Pentru testing**: Rulează cu date mici mai întâi

## 📝 Notes

- Folosește `.venv` pentru dependențe
- Import-uri sunt globale (nu relative)
- FastAPI e integrat (nu mai folosim uvicorn direct)
- Logs sunt configurate automat
