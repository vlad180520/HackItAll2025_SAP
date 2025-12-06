# Backend Architecture - Refactored Structure

## Overview

The backend has been refactored into a clean, modular structure with separated concerns:

```
backend/
├── main.py                 # FastAPI app initialization
├── routes/                  # API route handlers
│   ├── __init__.py
│   ├── simulation_routes.py  # POST /api/start
│   ├── status_routes.py      # GET /api/status, /api/inventory, /api/history
│   └── logs_routes.py        # GET /api/logs
├── services/                 # Business logic layer
│   ├── __init__.py
│   ├── singleton.py          # Singleton pattern for shared services
│   └── simulation_service.py # Simulation management service
├── schemas/                  # Pydantic models for API
│   ├── __init__.py
│   ├── simulation_schemas.py # StartSimulationRequest, SimulationStatusResponse
│   ├── status_schemas.py     # StatusResponse, InventoryResponse, HistoryResponse
│   └── logs_schemas.py       # LogsResponse
├── models/                   # Domain models (unchanged)
├── config.py                 # Configuration (unchanged)
├── api_client.py             # External API client (unchanged)
├── data_loader.py            # CSV data loader (unchanged)
├── state_manager.py          # State management (unchanged)
├── cost_calculator.py        # Cost calculations (unchanged)
├── validator.py              # Validation (unchanged)
├── optimizer.py              # Greedy optimizer (unchanged)
├── simulation_runner.py      # Simulation orchestration (unchanged)
└── logger.py                 # Logging (unchanged)
```

## Route Organization

### Simulation Routes (`routes/simulation_routes.py`)
- **POST** `/api/start` - Start simulation

### Status Routes (`routes/status_routes.py`)
- **GET** `/api/status` - Get simulation status
- **GET** `/api/inventory` - Get current inventories
- **GET** `/api/history` - Get decision and cost history

### Logs Routes (`routes/logs_routes.py`)
- **GET** `/api/logs` - Get simulation logs

## Service Layer

### SimulationService (`services/simulation_service.py`)
Centralized service for managing simulation state:
- `initialize_simulation()` - Initialize components
- `get_status()` - Get current status
- `get_inventory()` - Get inventories
- `get_history()` - Get history
- `start_simulation(api_key)` - Start simulation
- `run_simulation_task(api_key)` - Background task execution

### Singleton Pattern (`services/singleton.py`)
Ensures all routes share the same service instance for state consistency.

## Schema Layer

All API request/response models are defined in `schemas/`:
- Request models: `StartSimulationRequest`
- Response models: `StatusResponse`, `InventoryResponse`, `HistoryResponse`, `LogsResponse`, `SimulationStatusResponse`

## Benefits of This Structure

1. **Separation of Concerns**: Routes handle HTTP, services handle business logic
2. **Modularity**: Each route file is focused on a specific resource
3. **Testability**: Services can be tested independently
4. **Maintainability**: Easy to add new routes or modify existing ones
5. **Type Safety**: Pydantic schemas ensure type validation
6. **Scalability**: Easy to add dependency injection, middleware, etc.

## Adding New Routes

To add a new route:

1. Create schema in `schemas/` (if needed)
2. Add service method in `services/simulation_service.py` (if needed)
3. Create route file in `routes/` or add to existing route file
4. Import and include router in `main.py`

Example:
```python
# routes/new_routes.py
from fastapi import APIRouter
from ..services.singleton import get_simulation_service

router = APIRouter(prefix="/api", tags=["new"])

@router.get("/new-endpoint")
async def new_endpoint():
    service = get_simulation_service()
    return {"data": service.get_something()}
```

Then in `main.py`:
```python
from .routes.new_routes import router as new_router
app.include_router(new_router)
```

## Future Improvements

- Add dependency injection (FastAPI Depends) instead of singleton
- Add authentication middleware
- Add request validation middleware
- Add rate limiting
- Add API versioning
- Add OpenAPI tags and descriptions

