"""Routes for status, inventory, and history endpoints."""

import logging
from fastapi import APIRouter
from ..schemas.status_schemas import StatusResponse, InventoryResponse, HistoryResponse
from ..services.singleton import get_simulation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status", response_model=StatusResponse)
async def get_status():
    """
    Get current simulation status.
    
    Returns:
        Current status including round, costs, recent penalties
    """
    simulation_service = get_simulation_service()
    status_data = simulation_service.get_status()
    return StatusResponse(**status_data)


@router.get("/inventory", response_model=InventoryResponse)
async def get_inventory():
    """
    Get current airport inventories.
    
    Returns:
        Current inventory state
    """
    simulation_service = get_simulation_service()
    inventory_data = simulation_service.get_inventory()
    return InventoryResponse(**inventory_data)


@router.get("/history", response_model=HistoryResponse)
async def get_history():
    """
    Get decision and cost history.
    
    Returns:
        Decision log and cost log
    """
    simulation_service = get_simulation_service()
    history_data = simulation_service.get_history()
    return HistoryResponse(**history_data)

