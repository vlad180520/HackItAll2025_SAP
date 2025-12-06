"""Precomputation utilities for genetic algorithm.

Helper functions to prepare data structures used across GA operations.
"""

from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from models.flight import Flight
from models.airport import Airport
from config import CLASS_TYPES, KIT_DEFINITIONS


def find_hub(airports: Dict[str, Airport]) -> Tuple[Optional[str], Optional[Airport]]:
    """Find the HUB airport.
    
    Returns:
        Tuple of (hub_code, hub_airport) or (None, None) if not found
    """
    for code, airport in airports.items():
        if airport.is_hub:
            return code, airport
    return None, None


def compute_hub_demand_in_horizon(
    flights: List[Flight],
    hub_code: str,
    now_hours: int,
    horizon_hours: int,
) -> Dict[str, int]:
    """Compute demand per class for flights departing from HUB within horizon.
    
    Args:
        flights: List of all flights
        hub_code: HUB airport code
        now_hours: Current time in hours
        horizon_hours: Planning horizon in hours
        
    Returns:
        Dictionary mapping class to total passenger demand
    """
    demand_per_class = defaultdict(int)
    horizon_end = now_hours + horizon_hours
    
    for flight in flights:
        if flight.origin == hub_code:
            dep_hours = flight.scheduled_departure.to_hours()
            if now_hours <= dep_hours < horizon_end:
                for class_type in CLASS_TYPES:
                    demand_per_class[class_type] += flight.planned_passengers.get(class_type, 0)
    
    return dict(demand_per_class)


def compute_viable_demand(
    flights: List[Flight],
    hub_code: str,
    hub_airport: Airport,
    now_hours: int,
    horizon_hours: int,
    class_type: str,
) -> int:
    """Compute viable demand: flights that can be served after purchase arrives.
    
    Args:
        flights: List of all flights
        hub_code: HUB airport code
        hub_airport: HUB airport object
        now_hours: Current time in hours
        horizon_hours: Planning horizon in hours
        class_type: Kit class type
        
    Returns:
        Total passenger demand for flights departing after ETA
    """
    lead_time = int(KIT_DEFINITIONS[class_type]["lead_time"])
    processing_time = hub_airport.processing_times.get(class_type, 0)
    eta_hours = now_hours + lead_time + processing_time
    horizon_end = now_hours + horizon_hours
    
    viable_demand = 0
    for flight in flights:
        if flight.origin == hub_code:
            dep_hours = flight.scheduled_departure.to_hours()
            if eta_hours <= dep_hours < horizon_end:
                viable_demand += flight.planned_passengers.get(class_type, 0)
    
    return viable_demand


def get_flight_dict(flights: List[Flight]) -> Dict[str, Flight]:
    """Create a dictionary mapping flight_id to Flight object."""
    return {f.flight_id: f for f in flights}


def sort_flights_chronologically(flights: List[Flight]) -> List[Flight]:
    """Sort flights by departure time (chronologically)."""
    return sorted(flights, key=lambda f: f.scheduled_departure.to_hours())

