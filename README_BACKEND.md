# Backend Architecture Documentation

## Overview

The backend is implemented in Python 3.10+ using FastAPI framework. It manages the airline kit optimization simulation, communicates with the external evaluation platform, and provides REST API endpoints for the frontend monitoring interface.

## Architecture

### Module Structure

```
backend/
├── __init__.py
├── config.py              # Configuration and constants
├── main.py                # FastAPI application
├── simulation_runner.py   # Main simulation orchestration
├── data_loader.py          # CSV parsing
├── api_client.py           # External API client
├── state_manager.py        # Game state management
├── cost_calculator.py      # Cost and penalty calculations
├── validator.py            # Pre-submission validation
├── optimizer.py            # Greedy decision optimizer
├── logger.py               # Logging and reporting
├── models/                 # Pydantic data models
│   ├── airport.py
│   ├── aircraft.py
│   ├── flight.py
│   ├── kit.py
│   └── game_state.py
└── tests/                  # Pytest test suite
```

## Data Flow

1. **Initialization**: Data loader reads CSVs → produces Airport, AircraftType, Flight template dictionaries
2. **State Initialization**: SimulationRunner initializes GameState with initial inventories from CSV
3. **Session Start**: API Client starts session with external evaluation platform
4. **Round Loop** (720 rounds):
   - Receive flight updates (SCHEDULED/CHECKED_IN/LANDED events) from API
   - State Manager updates inventories and pending movements
   - Optimizer produces kit load decisions and purchase orders
   - Validator checks decisions for errors/warnings
   - Cost Calculator estimates costs
   - API Client submits play_round and receives penalties + next flight updates
   - Logger records all data
   - State Manager advances time
5. **Finalization**: Generate final report, stop session

## Key Components

### Configuration (`config.py`)

Centralizes all constants, penalty factors, and settings:
- Game constants: `TOTAL_ROUNDS = 720`, `MIN_START_HOUR = 4`
- Penalty factors: `NEGATIVE_INVENTORY_FACTOR = 1000.0`, etc.
- Kit definitions: cost, weight, lead_time per class
- API configuration: base URL, endpoints, API key header
- Optimizer parameters: `SAFETY_BUFFER`, `REORDER_THRESHOLD`, `TARGET_STOCK_LEVEL`, `LOOKAHEAD_HOURS`

Uses `pydantic.BaseSettings` for environment variable support via `.env` file.

### Data Models (`models/`)

All domain entities use Pydantic `BaseModel` for validation and JSON serialization:
- `Airport`: airport properties, storage capacity, costs, inventory
- `AircraftType`: passenger/kit capacity, fuel cost
- `Flight`: scheduled/actual departure/arrival, passengers, distance
- `KitLoadDecision`: flight_id and kits_per_class
- `KitPurchaseOrder`: kits_per_class, order_time, expected_delivery
- `GameState`: current time, inventories, movements, costs, penalties, flight history

### Data Loader (`data_loader.py`)

Parses CSV files using pandas:
- `load_airports()`: airports_with_stocks.csv → dict[str, Airport]
- `load_aircraft_types()`: aircraft_types.csv → dict[str, AircraftType]
- `load_flight_schedule()`: flight_plan.csv → dict[str, dict] (templates)

Uses conservative defaults for missing columns (see ASSUMPTIONS.md).

### API Client (`api_client.py`)

HTTP client for external evaluation platform:
- `start_session(api_key)`: POST /api/session/start
- `play_round(api_key, session_id, day, hour, kit_loads, purchases)`: POST /api/session/play
- `stop_session(api_key, session_id)`: POST /api/session/stop

Features:
- Retry logic with exponential backoff (max 3 retries)
- Custom `ValidationError` exception for HTTP 400
- Timeout handling (30 seconds default)

### State Manager (`state_manager.py`)

Manages game state transitions:
- `apply_kit_loads()`: Decrements departure inventory, creates pending arrival movements
- `apply_purchases()`: Creates pending delivery movements to HUB
- `advance_time_to()`: Processes movements due at target time, handles processing queues
- `get_inventory()`: Query current inventory
- `check_negative_inventories()`: Detect negative inventory violations

**Critical**: Processing time > turnaround time means kits from outbound flight are NOT available for return flight at outstation.

### Cost Calculator (`cost_calculator.py`)

Pure functions computing costs per README formulas:
- `calculate_loading_cost()`: Per-kit loading cost at departure airport
- `calculate_movement_cost()`: Fuel cost based on weight and distance
- `calculate_processing_cost()`: Per-kit processing cost at arrival airport
- `calculate_purchase_cost()`: Kit purchase cost
- Penalty functions: understock, overstock, plane overload, unfulfilled passengers
- `calculate_round_costs()`: Aggregates all costs for a round

All formulas must match README.md exactly.

### Validator (`validator.py`)

Pre-submission validation:
- Checks flight_id exists
- Validates aircraft capacity not exceeded per class
- Verifies departure inventory sufficient
- Ensures purchases only at HUB
- Validates timing (no past orders)

Returns `ValidationReport` with errors, warnings, and estimated penalty.

### Optimizer (`optimizer.py`)

Greedy rule-based optimizer:
- **Strategy**:
  - For each departing flight: load `min(aircraft_kit_capacity[class], max(planned_passengers[class], 0))`
  - If inventory insufficient, load what's available (allow zero)
  - For HUB purchases: if projected inventory for next 24 hours < `REORDER_THRESHOLD`, order up to `TARGET_STOCK_LEVEL`
- **Parameters** (configurable in `config.py`):
  - `SAFETY_BUFFER = 0`: No extra kits beyond passenger count
  - `REORDER_THRESHOLD = 10`: Trigger purchase when inventory drops below
  - `TARGET_STOCK_LEVEL = 50`: Purchase up to this level
  - `LOOKAHEAD_HOURS = 24`: Check flights departing in next 24 hours

Returns decisions, purchases, and rationale string for logging.

### Simulation Runner (`simulation_runner.py`)

Orchestrates the 720-round simulation:
- Initializes all components
- Starts session with external API
- Main loop:
  - Gets visible flights for current hour
  - Calls optimizer
  - Validates decisions
  - Submits to API
  - Updates state from response
  - Advances time
- Stops session and generates final report

### Logger (`logger.py`)

Structured logging:
- `configure_logging()`: Setup file and console handlers
- `JSONLogger`: Machine-parseable JSON log format
- `generate_final_report()`: JSON and text summary with cost breakdown, penalty analysis

### FastAPI Application (`main.py`)

REST API endpoints:
- `GET /status`: Current simulation status (round, costs, recent penalties)
- `GET /inventory`: Current airport inventories
- `GET /history`: Decision and cost history
- `POST /start`: Trigger simulation run (async background task)
- `GET /logs`: Stream simulation logs (placeholder)

Uses CORS middleware for frontend communication.

## Configuration Options

### Environment Variables (`.env` file)

```env
API_BASE_URL=http://localhost:8080
API_KEY_HEADER=API-KEY
SAFETY_BUFFER=0
REORDER_THRESHOLD=10
TARGET_STOCK_LEVEL=50
LOOKAHEAD_HOURS=24
LOG_LEVEL=INFO
LOG_FILE=simulation.log
```

### CSV File Paths

Default paths (relative to project root):
- `eval-platform/src/main/resources/liquibase/data/airports_with_stocks.csv`
- `eval-platform/src/main/resources/liquibase/data/aircraft_types.csv`
- `eval-platform/src/main/resources/liquibase/data/flight_plan.csv`

## Running the Backend

### Setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # Set API_KEY and other config
```

### Run Tests

```bash
pytest backend/tests/
```

### Start FastAPI Server

```bash
uvicorn backend.main:app --reload
```

Server runs on `http://localhost:8000`

### Run Simulation Directly

```bash
python -m backend.simulation_runner --api-key YOUR_KEY
```

## Greedy Strategy Explanation

The greedy optimizer is a simple, deterministic baseline that:

1. **Reacts to immediate needs**: Loads kits based on current flight passenger counts
2. **No forecasting**: Uses simple lookahead (24 hours) for purchase decisions
3. **Penalty avoidance priority**: Tries to avoid negative inventory and capacity violations
4. **Deterministic**: Same inputs produce same outputs (reproducible)

This provides a working baseline that can be enhanced later with:
- Predictive forecasting
- Machine learning optimizers
- Multi-objective optimization
- Advanced inventory management strategies

## Testing

Test suite covers:
- Data loader: CSV parsing with missing columns
- State manager: Kit loads, movements, processing transitions
- Cost calculator: Formula verification with handcrafted examples
- Validator: Capacity violations, invalid purchases
- Optimizer: Greedy logic produces valid decisions

Run with: `pytest backend/tests/`

## Error Handling

- **Validation errors**: Logged and simulation stops
- **API errors**: Retry with exponential backoff (max 3 retries)
- **Missing CSV columns**: Use conservative defaults, log warnings
- **Negative inventory**: Detected and logged, penalties applied

## Performance Considerations

- State manager uses O(1) dictionary lookups for inventories
- Optimizer processes flights in O(n) where n = visible flights
- Cost calculator uses pure functions (no side effects)
- Logger writes asynchronously to avoid blocking

## Future Enhancements

- Advanced optimizers (ML, predictive)
- Real-time streaming logs via WebSocket
- Database persistence for state
- Distributed simulation support
- Advanced analytics and reporting

