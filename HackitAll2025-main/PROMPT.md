Technology Stack

- Backend: Python with FastAPI framework
- Frontend: React with Vite build tool
- Backend communicates with external evaluation platform REST API (Java Spring Boot)
- Frontend visualizes optimization results and provides monitoring interface

General Constraints

- Backend implementation: Python 3.10+ with FastAPI for serving results/monitoring endpoints, requests library for external API calls, pandas for CSV parsing, pydantic for data models
- Frontend implementation: React 18+ with Vite, TypeScript recommended, fetch API for backend communication, chart libraries for visualization (e.g., recharts, chart.js)
- Choose the simpler implementation approach: greedy baseline, rule-based, deterministic. The agent should implement a working minimal solution that can be enhanced later.
- Code must be modular, well organized, and separate components clearly (configuration, models, data loader, API client, state manager, cost calculator, optimizer, validator, simulation runner, utils, tests, documentation).
- Avoid assumptions about external environment beyond what is explicitly stated in the repository documentation (README.md and html/index.html). If a missing detail is required, the agent must note it and proceed with a conservative default, and document the assumption.

Prompt (modular file list)

BACKEND IMPLEMENTATION (Python + FastAPI)

(1) CONFIGURATION

backend/config.py
- Purpose: centralize all constants, rule parameters and file paths used by the solution.
- Implementation: Python module with constants and a Config class using pydantic BaseSettings for environment variable support.
- Contents and responsibilities:
  - Game constants: TOTAL_ROUNDS = 720, MIN_START_HOUR = 4, CLASS_TYPES = ["FIRST", "BUSINESS", "PREMIUM_ECONOMY", "ECONOMY"].
  - Penalty factors and names exactly as described in the repository (NEGATIVE_INVENTORY_FACTOR, OVER_CAPACITY_FACTOR, FLIGHT_OVERLOAD_FACTOR, UNFULFILLED_PASSENGERS_FACTOR, INCORRECT_FLIGHT_LOAD_FACTOR, END_OF_GAME factors).
  - Kit definitions: dictionaries mapping class to cost, weight, lead_time.
  - File path constants for input CSVs relative to project root (eval-platform/src/main/resources/liquibase/data/).
  - External API configuration: BASE_URL, ENDPOINTS dict, API_KEY_HEADER = "API-KEY".
- Interface: importable module with typed constants. Example: from backend.config import Config, PENALTY_FACTORS, KIT_DEFINITIONS

(2) MODELS

backend/models/
- Purpose: represent domain entities using pydantic models for validation and serialization.
- Required model files:

backend/models/airport.py
- Airport (BaseModel): code: str, name: str, is_hub: bool, storage_capacity: dict[str, int], loading_costs: dict[str, float], processing_costs: dict[str, float], processing_times: dict[str, int], current_inventory: dict[str, int] = Field(default_factory=dict)

backend/models/aircraft.py
- AircraftType (BaseModel): type_code: str, passenger_capacity: dict[str, int], kit_capacity: dict[str, int], fuel_cost_per_km: float

backend/models/flight.py
- ReferenceHour (BaseModel): day: int, hour: int
- Flight (BaseModel): flight_id: str, flight_number: str, origin: str, destination: str, scheduled_departure: ReferenceHour, scheduled_arrival: ReferenceHour, planned_passengers: dict[str, int], planned_distance: float, aircraft_type: str, actual_departure: Optional[ReferenceHour], actual_arrival: Optional[ReferenceHour], actual_passengers: Optional[dict[str, int]], actual_distance: Optional[float], event_type: str

backend/models/kit.py
- KitType (BaseModel): class_id: str, cost: float, weight: float, lead_time: int
- KitLoadDecision (BaseModel): flight_id: str, kits_per_class: dict[str, int]
- KitPurchaseOrder (BaseModel): kits_per_class: dict[str, int], order_time: ReferenceHour, expected_delivery: ReferenceHour

backend/models/game_state.py
- KitMovement (BaseModel): movement_type: str, airport: str, kits_per_class: dict[str, int], execute_time: ReferenceHour
- PenaltyRecord (BaseModel): code: str, cost: float, reason: str, issued_time: ReferenceHour
- GameState (BaseModel): current_day: int, current_hour: int, airport_inventories: dict[str, dict[str, int]], in_process_kits: dict[str, list[KitMovement]], pending_movements: list[KitMovement], total_cost: float, penalty_log: list[PenaltyRecord], flight_history: list[Flight]

- Interface: all models inherit from pydantic BaseModel with .dict() and .parse_obj() methods for JSON serialization.

(3) DATA_LOADER

backend/data_loader.py
- Purpose: parse provided CSVs using pandas and produce model instances.
- Implementation: Python module with functions using pandas.read_csv().
- Responsibilities:
  - load_airports(csv_path: str) -> dict[str, Airport]: parse airports_with_stocks.csv
  - load_aircraft_types(csv_path: str) -> dict[str, AircraftType]: parse aircraft_types.csv
  - load_flight_schedule(csv_path: str) -> dict[str, dict]: parse flight_plan.csv into templates
  - Validate required columns exist; use conservative defaults (0 or empty dict) for missing per-class fields and log warnings.
- Interface: returns typed dictionaries keyed by code/number for O(1) lookup.

(4) API_CLIENT

backend/api_client.py
- Purpose: HTTP client for external evaluation platform using requests library.
- Implementation: Python class ExternalAPIClient with methods.
- Responsibilities:
  - start_session(api_key: str) -> dict: POST to /api/session/start, return session data
  - play_round(api_key: str, session_id: str, day: int, hour: int, kit_loads: list[dict], purchases: list[dict]) -> dict: POST to /api/session/play
  - stop_session(api_key: str, session_id: str) -> dict: POST to /api/session/stop
- Behavior and errors:
  - Raise custom exceptions for HTTP 400 (ValidationError with details from response)
  - For HTTP 200 with penalties: return full response including penalty array
  - Always include API-KEY header
  - Timeout and retry logic with exponential backoff (max 3 retries)
- Interface: class with typed method signatures returning parsed JSON dicts. Example: client = ExternalAPIClient(base_url); response = client.play_round(...)

(5) STATE_MANAGER

backend/state_manager.py
- Purpose: manage GameState transitions and time-based kit movements.
- Implementation: Python class StateManager.
- Responsibilities:
  - __init__(initial_state: GameState)
  - apply_kit_loads(decisions: list[KitLoadDecision], flights: list[Flight]) -> None: decrement departure airport inventory, create pending movements for landing
  - apply_purchases(orders: list[KitPurchaseOrder]) -> None: create pending delivery movements to HUB
  - advance_time_to(day: int, hour: int) -> None: process all movements with execute_time <= (day, hour), handle processing queue transitions
  - get_inventory(airport_code: str, kit_class: str) -> int: query current inventory
  - get_available_inventory(airport_code: str, kit_class: str) -> int: inventory minus reserved (pending departures)
  - check_negative_inventories() -> list[tuple[str, str, int]]: return list of (airport, class, negative_amount)
- Interface: class with methods mutating internal GameState. Expose read-only state via properties.

(6) COST_CALCULATOR

backend/cost_calculator.py
- Purpose: compute costs and penalties per README formulas.
- Implementation: Python module with pure functions.
- Responsibilities:
  - calculate_loading_cost(flight: Flight, kits: dict[str, int], airport: Airport) -> float
  - calculate_movement_cost(flight: Flight, kits: dict[str, int], aircraft: AircraftType, kit_defs: dict) -> float
  - calculate_processing_cost(flight: Flight, kits: dict[str, int], airport: Airport) -> float
  - calculate_purchase_cost(kits: dict[str, int], kit_defs: dict) -> float
  - calculate_understock_penalty(airport: Airport, inventory: dict[str, int]) -> float
  - calculate_overstock_penalty(airport: Airport, inventory: dict[str, int]) -> float
  - calculate_plane_overload_penalty(flight: Flight, kits: dict[str, int], aircraft: AircraftType, kit_defs: dict) -> float
  - calculate_unfulfilled_passengers_penalty(flight: Flight, kits: dict[str, int], kit_defs: dict) -> float
  - calculate_round_costs(state: GameState, decisions: list[KitLoadDecision], purchases: list[KitPurchaseOrder], airports: dict, aircraft: dict, flights: list[Flight]) -> dict: return breakdown
- Interface: pure functions returning float or dict. All formulas must match README exactly.

(7) VALIDATOR

backend/validator.py
- Purpose: pre-submission validation with detailed warnings/errors.
- Implementation: Python class Validator.
- Responsibilities:
  - __init__(airports: dict, aircraft: dict, kit_defs: dict)
  - validate_decisions(decisions: list[KitLoadDecision], purchases: list[KitPurchaseOrder], state: GameState, flights: list[Flight]) -> ValidationReport
  - ValidationReport (pydantic model): errors: list[str], warnings: list[str], estimated_penalty: float
  - Check: flight_id exists, aircraft capacity not exceeded per class, departure inventory sufficient, purchases only at HUB, timing valid
- Interface: validator = Validator(...); report = validator.validate_decisions(...)

(8) OPTIMIZER (greedy baseline)

backend/optimizer.py
- Purpose: produce decisions using simple greedy rule-based logic.
- Implementation: Python class GreedyOptimizer.
- Strategy specification:
  - decide(state: GameState, visible_flights: list[Flight], airports: dict, aircraft: dict) -> tuple[list[KitLoadDecision], list[KitPurchaseOrder], str]:
    - For each departing flight: load min(aircraft_kit_capacity[class], max(planned_passengers[class], 0))
    - If inventory insufficient, load what's available (allow zero)
    - For HUB purchases: if projected inventory for next 24 hours < reorder_threshold (config parameter, default 10 per class), order up to target_stock_level (config parameter, default 50 per class)
  - Parameters: SAFETY_BUFFER=0, REORDER_THRESHOLD=10, TARGET_STOCK_LEVEL=50, LOOKAHEAD_HOURS=24
  - Return rationale string explaining decisions for logging
- Interface: optimizer = GreedyOptimizer(config); decisions, purchases, rationale = optimizer.decide(...)

(9) SIMULATION_RUNNER

backend/simulation_runner.py
- Purpose: orchestrate the 720-round simulation loop.
- Implementation: Python class SimulationRunner.
- Responsibilities:
  - __init__(api_client, state_manager, optimizer, validator, cost_calculator, logger, airports, aircraft, kit_defs)
  - run(api_key: str, max_rounds: int = 720) -> dict: main loop
    - Start session
    - For each round:
      - Parse flight updates from API response and update state
      - Get visible flights for current hour
      - Call optimizer.decide()
      - Call validator.validate_decisions()
      - If fatal errors, log and stop; if warnings, log and proceed
      - Call api_client.play_round()
      - Log response, update state with penalties
      - Advance time
    - Return final report dict with costs, penalties, decision log
  - handle_errors(exception) -> None: log errors and decide whether to retry or stop
- Interface: runner = SimulationRunner(...); final_report = runner.run(api_key="...")

(10) LOGGING AND REPORTING

backend/logger.py
- Purpose: structured logging and report generation.
- Implementation: Python module using standard logging library + custom JSONLogger.
- Responsibilities:
  - configure_logging(level: str, log_file: str): setup file and console handlers
  - log_round(round_num: int, decisions: dict, costs: dict, penalties: list, inventory_snapshot: dict): append to structured log
  - generate_final_report(log_data: list, output_path: str): write JSON and text summary with cost breakdown, penalty analysis, decision timeline
- Interface: from backend.logger import log_round, generate_final_report

(11) TESTS

backend/tests/
- Purpose: pytest test suite for backend logic.
- Required test files:
  - tests/test_data_loader.py: verify CSV parsing produces non-empty dicts
  - tests/test_state_manager.py: test kit load, movement, processing transitions
  - tests/test_cost_calculator.py: verify formulas with handcrafted examples
  - tests/test_validator.py: detect capacity violations, invalid purchases
  - tests/test_optimizer.py: verify greedy logic produces valid decisions
- Run with: pytest backend/tests/

(12) BACKEND API (FastAPI server)

backend/main.py
- Purpose: FastAPI application exposing monitoring endpoints.
- Endpoints:
  - GET /status: return current simulation status (round, costs, recent penalties)
  - GET /inventory: return current airport inventories
  - GET /history: return decision and cost history
  - POST /start: trigger simulation run (async task)
  - GET /logs: stream simulation logs
- Implementation: FastAPI app with CORS middleware for frontend, background task for simulation_runner
- Run with: uvicorn backend.main:app --reload

backend/requirements.txt
- fastapi
- uvicorn[standard]
- pydantic
- pandas
- requests
- pytest
- python-dotenv

FRONTEND IMPLEMENTATION (React + Vite)

(13) FRONTEND PROJECT STRUCTURE

frontend/ (created with: npm create vite@latest frontend -- --template react-ts)

frontend/src/components/
- Dashboard.tsx: main layout with tabs for real-time monitoring, cost charts, inventory levels
- FlightTable.tsx: display flight events and decisions
- InventoryChart.tsx: bar/line charts showing inventory levels per airport
- CostBreakdown.tsx: pie chart of operational vs penalty costs
- PenaltyLog.tsx: table of all penalties with filtering

frontend/src/services/
- api.ts: fetch wrapper for backend API endpoints
  - getStatus(): Promise<StatusResponse>
  - getInventory(): Promise<InventoryResponse>
  - getHistory(): Promise<HistoryResponse>
  - startSimulation(apiKey: string): Promise<void>

frontend/src/types/
- types.ts: TypeScript interfaces matching backend pydantic models (Airport, Flight, GameState, etc.)

frontend/src/App.tsx
- Main app component with routing (if needed) or single-page dashboard

frontend/vite.config.ts
- Configure proxy to backend: server: { proxy: { '/api': 'http://localhost:8000' } }

frontend/package.json
- Dependencies: react, react-dom, recharts (or chart.js), axios (or native fetch)
- Scripts: dev, build, preview

(14) DOCUMENTATION

README_BACKEND.md
- Backend architecture overview
- Module descriptions and data flow
- Configuration options (environment variables, optimizer parameters)
- How to run: python -m backend.simulation_runner --api-key YOUR_KEY
- How to test: pytest backend/tests/
- Greedy strategy explanation and parameters

README_FRONTEND.md
- Frontend architecture overview
- Component structure and data flow
- How to run: npm run dev
- How to build: npm run build
- API integration details

ASSUMPTIONS.md
- List any missing CSV column names and defaults used
- Conservative defaults chosen (e.g., if processing_time missing, use 2 hours)
- Rationale for greedy optimizer parameters (buffer=0, threshold=10, target=50)

Implementation Guidance and Constraints

Backend (Python + FastAPI)
- Use type hints throughout (PEP 484)
- Use pydantic models for all data validation and serialization
- Keep modules small and single-responsibility
- Store configuration in environment variables (.env file) loaded via python-dotenv
- Use structured logging (JSON format for machine parsing)
- Write docstrings for all public functions and classes
- Handle errors explicitly: raise custom exceptions with clear messages
- Use pandas for CSV operations, requests for HTTP, pytest for tests
- Backend API (FastAPI) should be non-blocking for long-running simulation (use BackgroundTasks)

Frontend (React + Vite + TypeScript)
- Use TypeScript for type safety
- Use functional components with hooks (useState, useEffect)
- Separate concerns: components for UI, services for API calls, types for interfaces
- Use chart library (recharts recommended for React integration)
- Implement real-time updates via polling (e.g., every 2 seconds to GET /status)
- Handle loading states and errors gracefully in UI
- Use CSS modules or styled-components for styling
- Build production bundle with: npm run build
- Serve via: npm run preview or deploy dist/ folder

Project Structure
```
HackitAll2025/
├── backend/
│   ├── __init__.py
│   ├── config.py
│   ├── main.py (FastAPI app)
│   ├── simulation_runner.py
│   ├── data_loader.py
│   ├── api_client.py
│   ├── state_manager.py
│   ├── cost_calculator.py
│   ├── validator.py
│   ├── optimizer.py
│   ├── logger.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── airport.py
│   │   ├── aircraft.py
│   │   ├── flight.py
│   │   ├── kit.py
│   │   └── game_state.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_data_loader.py
│   │   ├── test_state_manager.py
│   │   ├── test_cost_calculator.py
│   │   ├── test_validator.py
│   │   └── test_optimizer.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── components/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── FlightTable.tsx
│   │   │   ├── InventoryChart.tsx
│   │   │   ├── CostBreakdown.tsx
│   │   │   └── PenaltyLog.tsx
│   │   ├── services/
│   │   │   └── api.ts
│   │   └── types/
│   │       └── types.ts
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
├── eval-platform/ (existing Java backend - read-only)
├── html/ (existing documentation - read-only)
├── README.md (existing - read-only)
├── PROMPT.md (this file)
├── README_BACKEND.md (to be created)
├── README_FRONTEND.md (to be created)
└── ASSUMPTIONS.md (to be created)
```

Running the Solution

1. Backend setup:
   ```bash
   cd backend
   pip install -r requirements.txt
   cp .env.example .env  # Set API_KEY and other config
   pytest tests/  # Run tests
   uvicorn main:app --reload  # Start FastAPI server on port 8000
   ```

2. Frontend setup:
   ```bash
   cd frontend
   npm install
   npm run dev  # Start Vite dev server on port 5173
   ```

3. Start simulation:
   - Via API: POST http://localhost:8000/start with {"api_key": "YOUR_KEY"}
   - Or direct: python -m backend.simulation_runner --api-key YOUR_KEY

Data Flow

1. Data Loader reads CSVs -> produces Airport, AircraftType, Flight template dicts
2. SimulationRunner initializes GameState with initial inventories
3. API Client starts session with external evaluation platform
4. Each round loop:
   - Receive flight updates (SCHEDULED/CHECKED_IN/LANDED events)
   - State Manager updates inventories and pending movements
   - Optimizer produces kit load decisions and purchase orders
   - Validator checks decisions for errors/warnings
   - Cost Calculator estimates costs
   - API Client submits play_round and receives penalties + next flight updates
   - Logger records all data
   - Frontend polls GET /status and updates charts
5. After 720 rounds: generate final report, display results

Conservative Defaults (if CSV data missing)

- If processing_time missing: use 2 hours per kit type
- If loading_cost missing: use 10.0 per kit
- If processing_cost missing: use 5.0 per kit
- If storage_capacity missing: use 100 per class
- If initial_inventory missing: use 50 per class at HUB, 20 at outstations
- Document all assumptions in ASSUMPTIONS.md

Greedy Optimizer Parameters

- SAFETY_BUFFER: 0 (no extra kits beyond passenger count)
- REORDER_THRESHOLD: 10 kits per class (trigger purchase when inventory drops below)
- TARGET_STOCK_LEVEL: 50 kits per class (purchase up to this level)
- LOOKAHEAD_HOURS: 24 (check flights departing in next 24 hours for purchase decisions)

These parameters are configurable in backend/config.py and can be tuned later.

Notes for the Implementer

- The greedy baseline is deliberately simple: it reacts to immediate needs without complex forecasting. This provides a working baseline that can be enhanced later with predictive or machine learning optimizers.
- Backend and frontend are decoupled: frontend polls backend API, backend manages simulation independently.
- External evaluation platform (Java Spring Boot) is read-only: solution only calls its REST API, does not modify it.
- CSV data is in eval-platform/src/main/resources/liquibase/data/ - load from there.
- All cost formulas must match README.md exactly - verify with small test cases.
- Processing time > turnaround time is critical: kits from outbound flight NOT available for return flight at outstation. Model this carefully in state_manager.
- Penalty avoidance is highest priority: penalties are much more expensive than operational costs.
- If missing CSV columns or unclear data, use conservative defaults and document in ASSUMPTIONS.md.
- When data is missing in CSVs or endpoints, do not crash: pick conservative defaults (0 for quantities, empty maps for missing per-class maps) and record the assumption in documentation.
- The greedy optimizer is the only required decision engine for now. Keep it simple and deterministic so that behaviour can be reproduced and debugged easily.
- Write clear rationale text for every decision returned by the optimizer explaining why numbers were chosen.
- Do not embed environment-specific configs (no absolute file paths or credentials); accept these as parameters to the run or config object.
- The prompt consumer should implement well-defined, testable units that can be executed in small steps (data load -> single round dry run -> multi-round run).
- This prompt chooses the greedy baseline method deliberately: it is minimal, safe, and does not make hidden assumptions about infrastructure or availability.
- If the implementer needs additional repository specifics (for example exact CSV column names not documented), they must list the missing fields and proceed with conservative defaults while documenting them.
- The agent implementing this prompt should produce code with clear separation between configuration, domain models, state transitions, decision logic, and I/O so that further optimizers or improvements can be added later.

