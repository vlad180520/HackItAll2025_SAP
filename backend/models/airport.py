"""Airport model."""

from typing import Dict
from pydantic import BaseModel, Field


class Airport(BaseModel):
    """Represents an airport with its properties and inventory."""
    
    code: str
    name: str
    is_hub: bool
    storage_capacity: Dict[str, int]  # per class
    loading_costs: Dict[str, float]  # per class
    processing_costs: Dict[str, float]  # per class
    processing_times: Dict[str, int]  # per class in hours
    current_inventory: Dict[str, int] = Field(default_factory=dict)  # per class
    
    class Config:
        json_schema_extra = {
            "example": {
                "code": "JFK",
                "name": "John F. Kennedy International Airport",
                "is_hub": True,
                "storage_capacity": {"FIRST": 100, "BUSINESS": 200, "PREMIUM_ECONOMY": 300, "ECONOMY": 500},
                "loading_costs": {"FIRST": 10.0, "BUSINESS": 8.0, "PREMIUM_ECONOMY": 6.0, "ECONOMY": 5.0},
                "processing_costs": {"FIRST": 5.0, "BUSINESS": 4.0, "PREMIUM_ECONOMY": 3.0, "ECONOMY": 2.0},
                "processing_times": {"FIRST": 2, "BUSINESS": 2, "PREMIUM_ECONOMY": 2, "ECONOMY": 2},
                "current_inventory": {"FIRST": 50, "BUSINESS": 50, "PREMIUM_ECONOMY": 50, "ECONOMY": 50},
            }
        }

