"""Aircraft model."""

from typing import Dict
from pydantic import BaseModel


class AircraftType(BaseModel):
    """Represents an aircraft type with capacity and fuel cost."""
    
    type_code: str
    passenger_capacity: Dict[str, int]  # per class
    kit_capacity: Dict[str, int]  # per class
    fuel_cost_per_km: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "type_code": "A320",
                "passenger_capacity": {"FIRST": 0, "BUSINESS": 20, "PREMIUM_ECONOMY": 30, "ECONOMY": 120},
                "kit_capacity": {"FIRST": 0, "BUSINESS": 20, "PREMIUM_ECONOMY": 30, "ECONOMY": 120},
                "fuel_cost_per_km": 0.5,
            }
        }

