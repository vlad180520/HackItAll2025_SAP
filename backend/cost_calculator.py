"""Cost calculator module for computing costs and penalties."""

import logging
from typing import Dict, List
from models.flight import Flight
from models.airport import Airport
from models.aircraft import AircraftType
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.game_state import GameState
from config import PENALTY_FACTORS, KIT_DEFINITIONS

logger = logging.getLogger(__name__)


def calculate_loading_cost(
    flight: Flight, kits: Dict[str, int], airport: Airport
) -> float:
    """
    Calculate loading cost for kits onto a flight.
    
    Args:
        flight: Flight object
        kits: Dictionary of kits per class
        airport: Departure airport
        
    Returns:
        Total loading cost
    """
    total_cost = 0.0
    
    for class_type, quantity in kits.items():
        if quantity > 0:
            cost_per_kit = airport.loading_costs.get(class_type, 10.0)
            total_cost += cost_per_kit * quantity
    
    return total_cost


def calculate_movement_cost(
    flight: Flight, kits: Dict[str, int], aircraft: AircraftType, kit_defs: Dict
) -> float:
    """
    Calculate movement cost (fuel cost based on weight and distance).
    
    Args:
        flight: Flight object
        kits: Dictionary of kits per class
        aircraft: Aircraft type
        kit_defs: Kit definitions dictionary
        
    Returns:
        Total movement cost
    """
    total_weight = 0.0
    
    for class_type, quantity in kits.items():
        if quantity > 0:
            kit_weight = kit_defs.get(class_type, {}).get("weight", 1.0)
            total_weight += kit_weight * quantity
    
    distance = flight.actual_distance or flight.planned_distance
    fuel_cost = aircraft.fuel_cost_per_km * distance
    
    # Movement cost is proportional to weight
    # Formula: fuel_cost * (1 + total_weight / base_weight)
    # Simplified: assume base weight is 1000kg
    base_weight = 1000.0
    movement_cost = fuel_cost * (1.0 + total_weight / base_weight)
    
    return movement_cost


def calculate_processing_cost(
    flight: Flight, kits: Dict[str, int], airport: Airport
) -> float:
    """
    Calculate processing cost for kits at arrival airport.
    
    Args:
        flight: Flight object
        kits: Dictionary of kits per class
        airport: Arrival airport
        
    Returns:
        Total processing cost
    """
    total_cost = 0.0
    
    for class_type, quantity in kits.items():
        if quantity > 0:
            cost_per_kit = airport.processing_costs.get(class_type, 5.0)
            total_cost += cost_per_kit * quantity
    
    return total_cost


def calculate_purchase_cost(kits: Dict[str, int], kit_defs: Dict) -> float:
    """
    Calculate purchase cost for kits.
    
    Args:
        kits: Dictionary of kits per class
        kit_defs: Kit definitions dictionary
        
    Returns:
        Total purchase cost
    """
    total_cost = 0.0
    
    for class_type, quantity in kits.items():
        if quantity > 0:
            kit_cost = kit_defs.get(class_type, {}).get("cost", 10.0)
            total_cost += kit_cost * quantity
    
    return total_cost


def calculate_understock_penalty(
    airport: Airport, inventory: Dict[str, int]
) -> float:
    """
    Calculate penalty for negative inventory (understock).
    
    Args:
        airport: Airport object
        inventory: Current inventory per class
        
    Returns:
        Total penalty cost
    """
    penalty = 0.0
    
    for class_type, quantity in inventory.items():
        if quantity < 0:
            penalty += abs(quantity) * PENALTY_FACTORS["NEGATIVE_INVENTORY"]
    
    return penalty


def calculate_overstock_penalty(
    airport: Airport, inventory: Dict[str, int]
) -> float:
    """
    Calculate penalty for exceeding storage capacity (overstock).
    
    Args:
        airport: Airport object
        inventory: Current inventory per class
        
    Returns:
        Total penalty cost
    """
    penalty = 0.0
    
    for class_type, quantity in inventory.items():
        capacity = airport.storage_capacity.get(class_type, 100)
        if quantity > capacity:
            excess = quantity - capacity
            penalty += excess * PENALTY_FACTORS["OVER_CAPACITY"]
    
    return penalty


def calculate_plane_overload_penalty(
    flight: Flight, kits: Dict[str, int], aircraft: AircraftType, kit_defs: Dict
) -> float:
    """
    Calculate penalty for exceeding aircraft kit capacity.
    
    Args:
        flight: Flight object
        kits: Dictionary of kits per class loaded
        aircraft: Aircraft type
        kit_defs: Kit definitions dictionary
        
    Returns:
        Total penalty cost
    """
    penalty = 0.0
    
    for class_type, quantity in kits.items():
        capacity = aircraft.kit_capacity.get(class_type, 0)
        if quantity > capacity:
            excess = quantity - capacity
            penalty += excess * PENALTY_FACTORS["FLIGHT_OVERLOAD"]
    
    return penalty


def calculate_unfulfilled_passengers_penalty(
    flight: Flight, kits: Dict[str, int], kit_defs: Dict
) -> float:
    """
    Calculate penalty for not loading enough kits for passengers.
    
    Args:
        flight: Flight object
        kits: Dictionary of kits per class loaded
        kit_defs: Kit definitions dictionary
        
    Returns:
        Total penalty cost
    """
    penalty = 0.0
    
    passengers = flight.actual_passengers or flight.planned_passengers
    
    for class_type, passenger_count in passengers.items():
        kit_count = kits.get(class_type, 0)
        if kit_count < passenger_count:
            unfulfilled = passenger_count - kit_count
            penalty += unfulfilled * PENALTY_FACTORS["UNFULFILLED_PASSENGERS"]
    
    return penalty


def calculate_round_costs(
    state: GameState,
    decisions: List[KitLoadDecision],
    purchases: List[KitPurchaseOrder],
    airports: Dict[str, Airport],
    aircraft: Dict[str, AircraftType],
    flights: List[Flight],
) -> Dict:
    """
    Calculate all costs for a round.
    
    Args:
        state: Current game state
        decisions: Kit load decisions
        purchases: Purchase orders
        airports: Dictionary of airports
        aircraft: Dictionary of aircraft types
        flights: List of flights in this round
        
    Returns:
        Dictionary with cost breakdown
    """
    flight_dict = {f.flight_id: f for f in flights}
    total_loading_cost = 0.0
    total_movement_cost = 0.0
    total_processing_cost = 0.0
    total_purchase_cost = 0.0
    total_penalties = 0.0
    
    # Calculate operational costs
    for decision in decisions:
        if decision.flight_id not in flight_dict:
            continue
        
        flight = flight_dict[decision.flight_id]
        origin_airport = airports.get(flight.origin)
        dest_airport = airports.get(flight.destination)
        aircraft_type = aircraft.get(flight.aircraft_type)
        
        if origin_airport:
            total_loading_cost += calculate_loading_cost(
                flight, decision.kits_per_class, origin_airport
            )
        
        if aircraft_type:
            total_movement_cost += calculate_movement_cost(
                flight, decision.kits_per_class, aircraft_type, KIT_DEFINITIONS
            )
        
        if dest_airport:
            total_processing_cost += calculate_processing_cost(
                flight, decision.kits_per_class, dest_airport
            )
    
    # Calculate purchase costs
    for purchase in purchases:
        total_purchase_cost += calculate_purchase_cost(
            purchase.kits_per_class, KIT_DEFINITIONS
        )
    
    # Calculate penalties from state
    for airport_code, inventory in state.airport_inventories.items():
        airport = airports.get(airport_code)
        if airport:
            total_penalties += calculate_understock_penalty(airport, inventory)
            total_penalties += calculate_overstock_penalty(airport, inventory)
    
    # Calculate flight-specific penalties
    for decision in decisions:
        if decision.flight_id not in flight_dict:
            continue
        
        flight = flight_dict[decision.flight_id]
        aircraft_type = aircraft.get(flight.aircraft_type)
        
        if aircraft_type:
            total_penalties += calculate_plane_overload_penalty(
                flight, decision.kits_per_class, aircraft_type, KIT_DEFINITIONS
            )
        
        total_penalties += calculate_unfulfilled_passengers_penalty(
            flight, decision.kits_per_class, KIT_DEFINITIONS
        )
    
    total_cost = (
        total_loading_cost
        + total_movement_cost
        + total_processing_cost
        + total_purchase_cost
        + total_penalties
    )
    
    return {
        "loading_cost": total_loading_cost,
        "movement_cost": total_movement_cost,
        "processing_cost": total_processing_cost,
        "purchase_cost": total_purchase_cost,
        "penalties": total_penalties,
        "total_cost": total_cost,
    }

