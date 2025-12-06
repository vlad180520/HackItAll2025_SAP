"""Schemas for status endpoints."""

from pydantic import BaseModel
from typing import Dict, List, Any, Union


class StatusResponse(BaseModel):
    """Response model for simulation status."""
    
    status: str
    round: int
    costs: Union[float, Dict[str, float]]
    penalties: List[Dict[str, Any]]


class InventoryResponse(BaseModel):
    """Response model for inventory data."""
    
    inventories: Dict[str, Dict[str, int]]


class HistoryResponse(BaseModel):
    """Response model for decision and cost history."""
    
    decision_log: List[Dict[str, Any]]
    cost_log: List[Dict[str, Any]]

