"""Schemas for simulation endpoints."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List


class StartSimulationRequest(BaseModel):
    """Request model for starting simulation."""
    
    api_key: str = Field(..., description="API key for authentication")


class SimulationStatusResponse(BaseModel):
    """Response model for simulation status."""
    
    message: str
    status: str
    session_id: Optional[str] = None

