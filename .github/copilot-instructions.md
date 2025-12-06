# AI Coding Agent Instructions - Airline Kit Management System

## Project Overview
A **hub-and-spoke airline rotables (passenger kit) optimization system** for the HackItAll 2025 SAP challenge. The system runs a 720-round simulation (30 days × 24 hours) minimizing operational costs while ensuring kit availability across airports.

**Key Domain Concepts:**
- **Rotables**: Reusable passenger kits (cutlery, pillows, headsets) that return to hub after processing
- **Hub-and-Spoke**: HUB1 (central) connects to outstations; only HUB can purchase new kits
- **Processing Times**: Kits need 6h (FIRST) to 1h (ECONOMY) before reuse
- **Lead Times**: New kit orders take 12-48h to arrive (class-dependent)

## Architecture: 3-Tier System

### Backend (Python/FastAPI)
```
backend/
├── main.py                    # FastAPI app with CORS, routes
├── simulation_runner.py       # Orchestrates 720-round loop (TEMPLATE - don't add logic here)
├── state_manager.py           # Game state transitions, kit movements tracking
├── api_client.py              # External evaluation platform client (retry logic)
├── data_loader.py             # CSV parsing (airports, aircraft, schedules)
├── solution/                  # ALL OPTIMIZATION LOGIC GOES HERE
│   ├── decision_maker.py      # Main orchestrator using SimpleLPStrategy
│   ├── config.py              # 30+ tunable parameters (buffers, thresholds, weights)
│   └── strategies/
│       ├── simple_lp_strategy.py  # Active: 389-line MILP solver (PuLP)
│       └── greedy_strategy.py     # Fallback heuristic
```

**Critical Pattern**: `SimulationRunner` is a **template/skeleton** - it handles API calls and validation but delegates ALL decision-making to `solution/` module. To change optimization logic, ONLY modify files in `solution/`.

### Frontend (React + TypeScript/Vite)
```
frontend/src/
├── components/
│   ├── Dashboard.tsx          # Main view controller (2s polling)
│   ├── FlightTable.tsx        # Upcoming flights with passenger counts
│   ├── InventoryChart.tsx     # Recharts bar chart (airport × class)
│   ├── CostBreakdown.tsx      # Operational vs penalty costs
│   ├── RoundCostTable.tsx     # Per-round cost history (last 50)
│   ├── PenaltyLog.tsx         # Real-time penalty stream
│   └── StatsCounter.tsx       # Cumulative decisions/purchases counter
├── services/api.ts            # Axios client with `/api` proxy
└── types/types.ts             # Shared TypeScript interfaces
```

**Proxy Pattern**: Vite dev server (`localhost:5173`) proxies `/api` to FastAPI (`localhost:8000`) - see `vite.config.ts`.

### External Platform (Java/Spring Boot)
`HackitAll2025-main/eval-platform/` - Evaluation server providing flight events (SCHEDULED → CHECKED_IN → LANDED). Our code submits load/purchase decisions via REST API.

## Critical Developer Workflows

### Running the System
```bash
# Backend (from backend/)
source .venv/bin/activate  # or use ./setup_venv.sh first time
python -m fastapi dev main.py --port 8000

# Frontend (from frontend/)
npm install  # first time only
npm run dev  # starts on localhost:5173

# Evaluation Platform (optional, from HackitAll2025-main/eval-platform/)
mvn spring-boot:run
```

**Important**: Backend uses `python -m fastapi dev` (NOT uvicorn directly) for hot-reload. Check `backend/run_server.sh` for reference.

### Modifying Optimization Strategy

**Quick Tuning** (most common):
1. Edit `backend/solution/config.py`:
   ```python
   HUB_REORDER_THRESHOLD: float = 0.25  # Buy when < 25% stock
   PASSENGER_BUFFER_PERCENT: float = 0.10  # Load 10% extra kits
   LOOKAHEAD_HOURS: int = 24  # Planning horizon
   ```

**Algorithm Changes**:
1. Edit `backend/solution/strategies/simple_lp_strategy.py`:
   - `_solve_milp()`: MILP problem formulation (constraints, objective)
   - `_simple_greedy()`: Fallback heuristic if PuLP unavailable
   - Uses PuLP for linear programming; falls back to greedy if solver fails

**Strategy Replacement**:
1. Edit `backend/solution/decision_maker.py` line 25-26:
   ```python
   self.strategy = SimpleLPStrategy(config=config, horizon_hours=72, solver_timeout_s=2)
   # Or: self.strategy = GreedyStrategy(config=config)
   ```

## Project-Specific Conventions

### Cost Formatting
- **Display**: European format `12.345,67` (thousand separator `.`, decimal `,`)
- **Storage**: Always `float` internally
- **Conversion**: Use `utils.format_cost(value)` for UI strings
- **Example**: `backend/services/simulation_service.py` returns both `costs` (numeric) and `costs_formatted` (string)

### State Management Pattern
```python
# StateManager.apply_kit_loads()
1. Decrement origin airport inventory
2. Create KitMovement with execute_time = arrival_time + processing_time
3. Add to pending_movements list

# StateManager.advance_time()
1. Move hour forward
2. Execute pending movements if execute_time <= current_time
3. Update in_process_kits and airport_inventories
```

**Why it matters**: Kits aren't instantly available - they're "in transit" or "processing" for hours. Optimizer must account for this delay.

### API Client Resilience
`ExternalAPIClient` in `api_client.py` has:
- Retry strategy: 3 attempts, exponential backoff
- HTTP 400 → raises `ValidationError` (decision rejected)
- HTTP 500-504 → auto-retry
- Always check for `ValidationError` when submitting decisions

### Data Loading Pattern
`data_loader.py` tries two paths:
1. Direct path (e.g., `data/airports.csv`)
2. Prefixed path (`HackitAll2025-main/data/airports.csv`)

This handles both standalone backend and full repo structures. Don't hardcode paths - use `_resolve_csv_path()`.

### Frontend Type Safety
All API responses defined in `types/types.ts`. Backend schemas in `backend/schemas/` use Pydantic. Keep them synchronized manually (no auto-generation currently).

## Testing & Validation

### Pre-Decision Validation
`backend/validator.py` checks:
- Flight exists and hasn't departed
- Kits ≤ aircraft capacity per class
- Purchase destination is HUB1 only

**Important**: External API also validates - `ValidationError` means rejected decision.

### Penalty System (see `backend/config.py`)
```python
UNFULFILLED_PASSENGERS_FACTOR = 300.0     # Missing kits for passengers
NEGATIVE_INVENTORY_FACTOR = 1000.0        # Airport stock < 0
FLIGHT_OVERLOAD_FACTOR = 2000.0           # Exceeded aircraft capacity
END_OF_GAME_NEGATIVE_INVENTORY = 2000.0   # Final stock penalties
```

**Strategy**: Optimizer heavily weights `slack` variables (10× multiplier) to avoid unfulfilled passengers - see `simple_lp_strategy.py` objective function.

## Integration Points

### Backend → External Platform
```python
# POST /api/round/{session_id}
{
  "loads": [{"flight_id": "...", "kits_per_class": {...}}],
  "purchases": [{"class_type": "FIRST", "quantity": 10}]
}

# Response includes:
- Flight events (SCHEDULED/CHECKED_IN/LANDED)
- Penalties issued this round
- Updated total cost
```

### Frontend → Backend
```typescript
// Polling every 2 seconds (Dashboard.tsx line 25)
GET /api/status          // Current round, costs, penalties
GET /api/inventory       // All airport stocks by class
GET /api/history?limit=50  // Recent round costs

// Control
POST /api/start {"api_key": "..."}  // Starts background simulation
POST /api/stop                       // Graceful shutdown
```

## Common Pitfalls

1. **Don't add optimization logic to `simulation_runner.py`** - it's a template. Use `solution/` module.
2. **Respect processing times** - kits loaded at hour H arrive at destination at H + flight_time but usable only at H + flight_time + processing_time.
3. **HUB1 is special** - only place to purchase, often has shortest processing times (6h vs 45h at outstations).
4. **Lead times vs processing times** - purchases have lead_time (24-48h), arrivals have processing_time (1-6h).
5. **Class capacity is separate** - aircraft has `kit_capacity["FIRST"]=10` but can't use spare FIRST slots for BUSINESS.
6. **Frontend uses European cost format** - always format costs for display via `format_cost()`.

## Key Files to Understand

- `backend/solution/ALGORITHM.md` - MILP formulation details
- `backend/models/game_state.py` - Core data structures (GameState, KitMovement)
- `backend/solution/config.py` - All tunable parameters with comments
- `HackitAll2025-main/README.md` - Problem statement and cost formulas
- `SIMPLIFICATION_CHANGES.md` - Recent refactoring rationale
