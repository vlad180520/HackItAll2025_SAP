"""Routes for simulation control (start, stop)."""

import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException
from ..schemas.simulation_schemas import StartSimulationRequest, SimulationStatusResponse
from ..services.singleton import get_simulation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["simulation"])


@router.post("/start", response_model=SimulationStatusResponse)
async def start_simulation(
    request: StartSimulationRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start simulation (runs in background).
    
    If an active session already exists for this API key, it will be stopped first.
    
    Args:
        request: Start simulation request with API key
        background_tasks: FastAPI background tasks
        
    Returns:
        Confirmation message
    """
    simulation_service = get_simulation_service()
    
    try:
        simulation_service.start_simulation(request.api_key, stop_existing=True)
        
        # Run simulation in background
        background_tasks.add_task(
            simulation_service.run_simulation_task,
            request.api_key
        )
        
        return SimulationStatusResponse(
            message="Simulation started",
            status="running"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting simulation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop", response_model=SimulationStatusResponse)
async def stop_simulation():
    """
    Stop the current simulation and end the session on evaluation platform.
    
    Returns:
        Confirmation message with final report
    """
    simulation_service = get_simulation_service()
    
    try:
        final_report = simulation_service.stop_simulation()
        return SimulationStatusResponse(
            message="Simulation stopped",
            status="completed"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error stopping simulation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
