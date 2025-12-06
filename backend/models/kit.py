"""Kit models."""

from typing import Dict
from pydantic import BaseModel
from .flight import ReferenceHour


class KitType(BaseModel):
    """Represents a kit type definition."""
    
    class_id: str
    cost: float
    weight: float
    lead_time: int  # hours


class KitLoadDecision(BaseModel):
    """Represents a decision to load kits onto a flight."""
    
    flight_id: str
    kits_per_class: Dict[str, int]
    
    class Config:
        json_schema_extra = {
            "example": {
                "flight_id": "FL001",
                "kits_per_class": {"FIRST": 10, "BUSINESS": 20, "PREMIUM_ECONOMY": 30, "ECONOMY": 100},
            }
        }


class KitPurchaseOrder(BaseModel):
    """Represents a purchase order for kits."""
    
    kits_per_class: Dict[str, int]
    order_time: ReferenceHour
    expected_delivery: ReferenceHour
    
    class Config:
        json_schema_extra = {
            "example": {
                "kits_per_class": {"FIRST": 20, "BUSINESS": 30, "PREMIUM_ECONOMY": 40, "ECONOMY": 100},
                "order_time": {"day": 0, "hour": 6},
                "expected_delivery": {"day": 1, "hour": 6},
            }
        }

