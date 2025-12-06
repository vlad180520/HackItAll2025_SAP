"""Game state model."""

from typing import Dict, List
from pydantic import BaseModel
from models.flight import Flight, ReferenceHour


class KitMovement(BaseModel):
    """Represents a kit movement (load, delivery, processing)."""
    
    movement_type: str  # "LOAD", "DELIVERY", "PROCESSING"
    airport: str
    kits_per_class: Dict[str, int]
    execute_time: ReferenceHour


class PenaltyRecord(BaseModel):
    """Represents a penalty issued by the system."""
    
    code: str
    cost: float
    reason: str
    issued_time: ReferenceHour


class GameState(BaseModel):
    """Represents the current state of the game."""
    
    current_day: int
    current_hour: int
    airport_inventories: Dict[str, Dict[str, int]]  # airport_code -> class -> quantity
    in_process_kits: Dict[str, List[KitMovement]]  # airport_code -> list of movements in processing
    pending_movements: List[KitMovement]
    total_cost: float
    penalty_log: List[PenaltyRecord]
    flight_history: List[Flight]
    
    def get_current_time(self) -> ReferenceHour:
        """Get current reference hour."""
        return ReferenceHour(day=self.current_day, hour=self.current_hour)
    
    class Config:
        json_schema_extra = {
            "example": {
                "current_day": 0,
                "current_hour": 4,
                "airport_inventories": {
                    "JFK": {"FIRST": 50, "BUSINESS": 50, "PREMIUM_ECONOMY": 50, "ECONOMY": 50},
                    "LAX": {"FIRST": 20, "BUSINESS": 20, "PREMIUM_ECONOMY": 20, "ECONOMY": 20},
                },
                "in_process_kits": {},
                "pending_movements": [],
                "total_cost": 0.0,
                "penalty_log": [],
                "flight_history": [],
            }
        }

