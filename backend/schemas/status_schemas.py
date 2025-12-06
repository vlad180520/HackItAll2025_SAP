"""Schemas for status endpoints."""

from pydantic import BaseModel, Field
from typing import Dict, List, Any, Union, Optional


class StatusResponse(BaseModel):
    """Response model for simulation status."""
    
    status: str
    round: int
    costs: Union[float, Dict[str, float]]
    costs_formatted: Optional[str] = Field(None, description="Formatted cost string with thousand separators")
    penalties: List[Dict[str, Any]]
    cumulative_decisions: int = 0
    cumulative_purchases: int = 0


class InventoryResponse(BaseModel):
    """Response model for inventory data."""
    
    inventories: Dict[str, Dict[str, int]]


class HistoryResponse(BaseModel):
    """Response model for decision and cost history."""
    
    decision_log: List[Dict[str, Any]]
    cost_log: List[Dict[str, Any]]
    total_rounds: int

