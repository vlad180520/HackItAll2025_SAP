"""Repair functions for genetic algorithm.

Ensures individuals are feasible by clamping loads and purchases
to respect capacity and availability constraints.
"""

from typing import Dict, List
from collections import defaultdict

from models.game_state import GameState
from models.flight import Flight
from models.airport import Airport
from models.aircraft import AircraftType
from config import CLASS_TYPES

from solution.strategies.genetic.types import Individual
from solution.strategies.genetic.precompute import find_hub, get_flight_dict


def repair_individual(
    individual: Individual,
    state: GameState,
    flights: List[Flight],
    airports: Dict[str, Airport],
    aircraft_types: Dict[str, AircraftType],
) -> None:
    """Repair an individual to ensure feasibility.
    
    Enforces:
    - Load quantities within aircraft capacity and available inventory
    - Purchase quantities within storage capacity limits
    - No negative inventories after operations
    
    Processes flights chronologically and tracks inventory usage.
    
    Args:
        individual: Individual to repair (modified in place)
        state: Current game state
        flights: List of flights
        airports: Airport dictionary
        aircraft_types: Aircraft type dictionary
    """
    # Build flight lookup
    flight_dict = get_flight_dict(flights)
    
    # Sort flights chronologically for proper inventory tracking
    sorted_flight_keys = sorted(
        [key for key in individual.genes.keys()],
        key=lambda k: flight_dict[k[0]].scheduled_departure.to_hours() if k[0] in flight_dict else 0
    )
    
    # Track inventory usage per airport
    inventory_usage = defaultdict(lambda: defaultdict(int))
    
    # Repair load genes chronologically
    for (flight_id, class_type) in sorted_flight_keys:
        load_qty = individual.genes.get((flight_id, class_type), 0)
        
        flight = flight_dict.get(flight_id)
        if not flight:
            individual.genes[(flight_id, class_type)] = 0
            continue
        
        aircraft = aircraft_types.get(flight.aircraft_type)
        if not aircraft:
            individual.genes[(flight_id, class_type)] = 0
            continue
        
        origin = flight.origin
        capacity = aircraft.kit_capacity.get(class_type, 0)
        available = state.airport_inventories.get(origin, {}).get(class_type, 0)
        available -= inventory_usage[origin][class_type]
        
        # Clip to feasible range: [0, min(capacity, available)]
        load_qty = max(0, min(load_qty, capacity, available))
        individual.genes[(flight_id, class_type)] = load_qty
        inventory_usage[origin][class_type] += load_qty
    
    # Repair purchase genes (HUB capacity constraint)
    hub_code, hub_airport = find_hub(airports)
    
    if hub_code and hub_airport:
        for class_type in CLASS_TYPES:
            purchase_qty = individual.purchase_genes.get(class_type, 0)
            
            # Storage capacity at HUB
            storage_capacity = hub_airport.storage_capacity.get(class_type, 1000)
            current_stock = state.airport_inventories.get(hub_code, {}).get(class_type, 0)
            
            # Maximum purchase = capacity - current_stock
            # Conservative: ensures we don't overflow even if no kits consumed
            max_purchase = max(0, storage_capacity - current_stock)
            
            # Clip purchase to feasible range
            individual.purchase_genes[class_type] = max(0, min(purchase_qty, max_purchase))

