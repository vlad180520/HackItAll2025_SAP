"""Flight model."""

from typing import Dict, Optional
from pydantic import BaseModel


class ReferenceHour(BaseModel):
    """Represents a reference hour (day and hour)."""
    
    day: int
    hour: int
    
    def __lt__(self, other: "ReferenceHour") -> bool:
        """Compare two reference hours for ordering."""
        if self.day != other.day:
            return self.day < other.day
        return self.hour < other.hour
    
    def __le__(self, other: "ReferenceHour") -> bool:
        """Less than or equal comparison."""
        return self < other or (self.day == other.day and self.hour == other.hour)
    
    def __gt__(self, other: "ReferenceHour") -> bool:
        """Greater than comparison."""
        return not self <= other
    
    def __ge__(self, other: "ReferenceHour") -> bool:
        """Greater than or equal comparison."""
        return not self < other
    
    def to_hours(self) -> int:
        """Convert to total hours since game start."""
        return self.day * 24 + self.hour


class Flight(BaseModel):
    """Represents a flight with scheduled and actual information."""
    
    flight_id: str
    flight_number: str
    origin: str
    destination: str
    scheduled_departure: ReferenceHour
    scheduled_arrival: ReferenceHour
    planned_passengers: Dict[str, int]  # per class
    planned_distance: float
    aircraft_type: str
    actual_departure: Optional[ReferenceHour] = None
    actual_arrival: Optional[ReferenceHour] = None
    actual_passengers: Optional[Dict[str, int]] = None
    actual_distance: Optional[float] = None
    event_type: str  # SCHEDULED, CHECKED_IN, LANDED
    
    class Config:
        json_schema_extra = {
            "example": {
                "flight_id": "FL001",
                "flight_number": "AA100",
                "origin": "JFK",
                "destination": "LAX",
                "scheduled_departure": {"day": 0, "hour": 6},
                "scheduled_arrival": {"day": 0, "hour": 12},
                "planned_passengers": {"FIRST": 10, "BUSINESS": 20, "PREMIUM_ECONOMY": 30, "ECONOMY": 100},
                "planned_distance": 4000.0,
                "aircraft_type": "A320",
                "event_type": "SCHEDULED",
            }
        }

