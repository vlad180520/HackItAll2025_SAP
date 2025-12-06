"""Schemas for logs endpoints."""

from pydantic import BaseModel
from typing import List, Dict, Any


class LogsResponse(BaseModel):
    """Response model for simulation logs."""
    
    logs: List[Dict[str, Any]]

