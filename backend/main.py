"""FastAPI main application for monitoring and control."""

import logging
from typing import Dict, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import Config
from .data_loader import load_airports, load_aircraft_types, load_flight_schedule
from .api_client import ExternalAPIClient
from .state_manager import StateManager
from .optimizer import GreedyOptimizer
from .validator import Validator
from .simulation_runner import SimulationRunner
from .models.game_state import GameState
from .config import KIT_DEFINITIONS, AIRPORTS_CSV, AIRCRAFT_TYPES_CSV, FLIGHT_PLAN_CSV
from .logger import configure_logging

# Configure logging
configure_logging()
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Airline Kit Management API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create API router with /api prefix
api_router = APIRouter(prefix="/api")

# Global state
config = Config()
simulation_state: Optional[Dict] = None
simulation_runner: Optional[SimulationRunner] = None


class StartSimulationRequest(BaseModel):
    """Request model for starting simulation."""
    api_key: str


def initialize_simulation() -> SimulationRunner:
    """
    Initialize simulation components.
    
    Returns:
        Initialized SimulationRunner
    """
    # Load data
    airports = load_airports(AIRPORTS_CSV, config)
    aircraft = load_aircraft_types(AIRCRAFT_TYPES_CSV)
    flight_templates = load_flight_schedule(FLIGHT_PLAN_CSV)
    
    # Initialize initial game state
    initial_inventories = {}
    for code, airport in airports.items():
        initial_inventories[code] = airport.current_inventory
    
    initial_state = GameState(
        current_day=0,
        current_hour=4,  # MIN_START_HOUR
        airport_inventories=initial_inventories,
        in_process_kits={},
        pending_movements=[],
        total_cost=0.0,
        penalty_log=[],
        flight_history=[],
    )
    
    # Initialize components
    api_client = ExternalAPIClient(
        base_url=config.API_BASE_URL,
        api_key_header=config.API_KEY_HEADER,
    )
    state_manager = StateManager(initial_state)
    optimizer = GreedyOptimizer(config)
    validator = Validator(airports, aircraft, KIT_DEFINITIONS)
    
    runner = SimulationRunner(
        api_client=api_client,
        state_manager=state_manager,
        optimizer=optimizer,
        validator=validator,
        airports=airports,
        aircraft=aircraft,
        kit_defs=KIT_DEFINITIONS,
        config=config,
    )
    
    return runner


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Airline Kit Management API", "status": "running"}


@api_router.get("/status")
async def get_status():
    """
    Get current simulation status.
    
    Returns:
        Current status including round, costs, recent penalties
    """
    if simulation_state is None:
        return {
            "status": "not_started",
            "round": 0,
            "costs": {},
            "penalties": [],
        }
    
    return {
        "status": "running" if simulation_runner else "completed",
        "round": simulation_state.get("rounds_completed", 0),
        "costs": simulation_state.get("total_cost", 0.0),
        "penalties": simulation_state.get("penalty_log", [])[-10:],  # Last 10 penalties
    }


@api_router.get("/inventory")
async def get_inventory():
    """
    Get current airport inventories.
    
    Returns:
        Current inventory state
    """
    if simulation_runner is None:
        return {"inventories": {}}
    
    state = simulation_runner.state_manager.current_state
    return {"inventories": state.airport_inventories}


@api_router.get("/history")
async def get_history():
    """
    Get decision and cost history.
    
    Returns:
        Decision log and cost log
    """
    if simulation_runner is None:
        return {"decision_log": [], "cost_log": []}
    
    return {
        "decision_log": simulation_runner.decision_log,
        "cost_log": simulation_runner.cost_log,
    }


@api_router.post("/start")
async def start_simulation(
    request: StartSimulationRequest, background_tasks: BackgroundTasks
):
    """
    Start simulation (runs in background).
    
    Args:
        request: Start simulation request with API key
        background_tasks: FastAPI background tasks
        
    Returns:
        Confirmation message
    """
    global simulation_runner, simulation_state
    
    if simulation_runner is not None:
        raise HTTPException(status_code=400, detail="Simulation already running")
    
    try:
        simulation_runner = initialize_simulation()
        
        # Run simulation in background
        background_tasks.add_task(run_simulation_task, request.api_key)
        
        return {"message": "Simulation started", "status": "running"}
    except Exception as e:
        logger.error(f"Error starting simulation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def run_simulation_task(api_key: str) -> None:
    """
    Background task to run simulation.
    
    Args:
        api_key: API key for authentication
    """
    global simulation_state
    
    try:
        logger.info("Starting simulation task")
        final_report = simulation_runner.run(api_key=api_key)
        simulation_state = final_report
        logger.info("Simulation task completed")
    except Exception as e:
        logger.error(f"Error in simulation task: {e}")
        simulation_state = {"error": str(e)}


@api_router.get("/logs")
async def get_logs():
    """
    Get simulation logs (streaming endpoint placeholder).
    
    Returns:
        Log entries
    """
    # In a real implementation, this would stream logs
    # For now, return recent log entries
    return {"logs": []}


# Include API router
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

