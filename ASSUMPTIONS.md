# Assumptions and Defaults

This document lists all assumptions made during implementation, missing CSV column names, and conservative defaults used when data is unavailable.

## CSV Data Assumptions

### Missing Column Names

The following CSV column names are assumed based on the data model requirements. If actual CSV files use different names, the data loader will use conservative defaults:

#### airports_with_stocks.csv

**Required columns:**
- `code`: Airport code (e.g., "JFK")
- `name`: Airport name
- `is_hub`: Boolean indicating if airport is a hub

**Per-class columns (for each class: FIRST, BUSINESS, PREMIUM_ECONOMY, ECONOMY):**
- `storage_capacity_{CLASS}`: Maximum storage capacity
- `loading_cost_{CLASS}`: Cost per kit to load onto aircraft
- `processing_cost_{CLASS}`: Cost per kit to process at arrival
- `processing_time_{CLASS}`: Hours required to process kits
- `initial_inventory_{CLASS}`: Starting inventory quantity

**Defaults if missing:**
- `storage_capacity`: 100 per class
- `loading_cost`: 10.0 per kit
- `processing_cost`: 5.0 per kit
- `processing_time`: 2 hours
- `initial_inventory`: 50 at HUB, 20 at outstations

#### aircraft_types.csv

**Required columns:**
- `type_code`: Aircraft type code (e.g., "A320")

**Per-class columns:**
- `passenger_capacity_{CLASS}`: Maximum passengers per class
- `kit_capacity_{CLASS}`: Maximum kits per class (assumed same as passenger capacity)

**Other columns:**
- `fuel_cost_per_km`: Fuel cost per kilometer

**Defaults if missing:**
- `passenger_capacity`: 0 per class
- `kit_capacity`: 0 per class
- `fuel_cost_per_km`: 0.5

#### flight_plan.csv

**Required columns:**
- `flight_id`: Unique flight identifier
- `flight_number`: Flight number (e.g., "AA100")
- `origin`: Departure airport code
- `destination`: Arrival airport code

**Time columns:**
- `scheduled_departure_day`: Day of departure
- `scheduled_departure_hour`: Hour of departure
- `scheduled_arrival_day`: Day of arrival
- `scheduled_arrival_hour`: Hour of arrival

**Per-class columns:**
- `planned_passengers_{CLASS}`: Expected passenger count per class

**Other columns:**
- `planned_distance`: Flight distance in kilometers
- `aircraft_type`: Aircraft type code

**Defaults if missing:**
- `scheduled_departure_day`: 0
- `scheduled_departure_hour`: 0
- `scheduled_arrival_day`: 0
- `scheduled_arrival_hour`: 0
- `planned_passengers`: 0 per class
- `planned_distance`: 0.0
- `aircraft_type`: "UNKNOWN"

## Processing Time Assumptions

**Critical assumption**: Processing time is assumed to be 2 hours per kit type by default. This is important because:

- Processing time > turnaround time means kits from outbound flight are NOT available for return flight at outstation
- This must be modeled carefully in `state_manager.py`
- If actual processing times differ, update `DEFAULT_PROCESSING_TIME` in `config.py`

## Greedy Optimizer Parameters

### Rationale for Default Values

**SAFETY_BUFFER = 0**
- No extra kits beyond passenger count
- Conservative approach: minimize inventory holding costs
- Can be increased if passenger count uncertainty is high

**REORDER_THRESHOLD = 10**
- Trigger purchase when inventory drops below 10 kits per class
- Balances between stockouts and overstocking
- Based on typical demand patterns (assumed)

**TARGET_STOCK_LEVEL = 50**
- Purchase up to 50 kits per class at HUB
- Provides buffer for demand variability
- Can be tuned based on historical demand

**LOOKAHEAD_HOURS = 24**
- Check flights departing in next 24 hours for purchase decisions
- Simple forecasting window
- Can be extended for better planning

These parameters are configurable in `backend/config.py` and can be tuned based on:
- Historical demand patterns
- Lead time variability
- Cost of stockouts vs. overstocking
- Simulation results

## API Assumptions

### External Evaluation Platform

**Base URL**: `http://localhost:8080` (default, configurable via environment variable)

**Endpoints**:
- `POST /api/session/start`: Returns `{session_id: string, ...}`
- `POST /api/session/play`: Accepts `{session_id, day, hour, kit_loads[], purchases[]}`, returns `{penalties[], flights[], inventories?, ...}`
- `POST /api/session/stop`: Accepts `{session_id}`, returns final report

**Response format assumptions**:
- Penalties array: `[{code: string, cost: number, reason: string}, ...]`
- Flights array: Flight objects matching `Flight` model
- Inventories (optional): `{airport_code: {class: quantity}, ...}`

**Error handling**:
- HTTP 400: Validation error (raises `ValidationError`)
- HTTP 200 with penalties: Normal response (penalties logged)
- Other HTTP errors: Retry with exponential backoff

## Game Rules Assumptions

### Time Progression
- Game starts at hour 4 (MIN_START_HOUR)
- Each round advances by 1 hour
- Total rounds: 720 (30 days × 24 hours)

### Kit Movements
- Kits loaded at departure are immediately deducted from origin inventory
- Kits arrive at destination at scheduled arrival time
- Kits enter processing queue at arrival (processing_time hours)
- Kits become available in inventory after processing completes

### Purchase Orders
- Purchases can only be made at HUB airports
- Lead time: 24 hours (from KIT_DEFINITIONS)
- Delivery adds kits directly to HUB inventory (no processing needed)

### Penalties
- Applied immediately when violations occur
- Logged in `penalty_log` with timestamp
- Added to `total_cost`

## Cost Formula Assumptions

All cost formulas must match README.md exactly. If README formulas are unclear:

- **Loading cost**: Per-kit cost at departure airport (from airport.loading_costs)
- **Movement cost**: Fuel cost × distance × (1 + weight_factor)
- **Processing cost**: Per-kit cost at arrival airport (from airport.processing_costs)
- **Purchase cost**: Per-kit cost from KIT_DEFINITIONS

Penalty factors are exact values from `config.py`:
- NEGATIVE_INVENTORY_FACTOR = 1000.0
- OVER_CAPACITY_FACTOR = 500.0
- FLIGHT_OVERLOAD_FACTOR = 2000.0
- UNFULFILLED_PASSENGERS_FACTOR = 300.0
- INCORRECT_FLIGHT_LOAD_FACTOR = 500.0
- END_OF_GAME factors: 2000.0 and 1000.0

## File Path Assumptions

CSV files are expected at:
- `eval-platform/src/main/resources/liquibase/data/airports_with_stocks.csv`
- `eval-platform/src/main/resources/liquibase/data/aircraft_types.csv`
- `eval-platform/src/main/resources/liquibase/data/flight_plan.csv`

If files are missing:
- Data loader logs warning
- Returns empty dictionaries
- Simulation may fail or use mock data

## Environment Assumptions

### Python
- Python 3.10+ required
- Virtual environment recommended
- Dependencies from `requirements.txt`

### Node.js
- Node.js 18+ recommended
- npm or yarn for package management

### Network
- Backend accessible at `http://localhost:8000`
- Frontend accessible at `http://localhost:5173`
- External evaluation platform at `http://localhost:8080` (configurable)

## Logging Assumptions

- Logs written to `simulation.log` (rotating, max 10MB, 5 backups)
- JSON logs written to `simulation.jsonl` (one JSON object per line)
- Log level: INFO (configurable via LOG_LEVEL environment variable)

## Testing Assumptions

- Tests use temporary CSV files (pytest fixtures)
- Mock external API calls (not implemented in current tests)
- Test data is minimal but representative

## Future Enhancements

When actual CSV files and API documentation are available:
1. Update column names in `data_loader.py`
2. Verify cost formulas match actual README
3. Adjust defaults based on real data
4. Update this document with actual assumptions

