"""Fitness evaluation for genetic algorithm.

Evaluates solutions based on:
- Operational costs (loading, processing, transport, purchase)
- Penalties (unfulfilled passengers, overload, inventory violations)

Penalty formulas match PenaltyFactors.java exactly:
- UnfulfilledKits = UNFULFILLED_FACTOR * distance * kitCost * unfulfilled_qty
- PlaneOverload = OVERLOAD_FACTOR * distance * fuelCost * kitCost * overload_qty
- NegativeInventory = NEGATIVE_INV_FACTOR * |negative_stock|
- OverCapacity = OVER_CAPACITY_FACTOR * overflow_qty

Uses timeline-aware inventory tracking where purchases become available
after lead_time + processing_time.
"""

from typing import Dict, List
from collections import defaultdict

from models.game_state import GameState
from models.flight import Flight
from models.airport import Airport
from models.aircraft import AircraftType
from config import CLASS_TYPES, KIT_DEFINITIONS, PENALTY_FACTORS

from solution.strategies.genetic.types import Individual
from solution.strategies.genetic.config import TRANSPORT_COST_SCALE
from solution.strategies.genetic.precompute import find_hub


def evaluate_fitness(
    individual: Individual,
    state: GameState,
    flights: List[Flight],
    airports: Dict[str, Airport],
    aircraft_types: Dict[str, AircraftType],
    now_hours: int,
) -> float:
    """Evaluate fitness with timeline-aware inventory tracking.
    
    Cost components:
    - Loading costs (airport-specific)
    - Processing costs (destination airport)
    - Transport costs (weight * distance * fuel_cost * scale)
    - Purchase costs (from KIT_DEFINITIONS)
    
    Penalties (from PENALTY_FACTORS):
    - UNFULFILLED_PASSENGERS: passengers not covered by kits
    - FLIGHT_OVERLOAD: kits exceed aircraft capacity
    - NEGATIVE_INVENTORY: inventory goes negative
    - OVER_CAPACITY: storage capacity exceeded
    
    Timeline:
    - Purchases at HUB available after: now + lead_time + processing_time
    - Only available stock counts for flight loads
    
    Args:
        individual: Solution to evaluate
        state: Current game state
        flights: List of flights
        airports: Airport dictionary
        aircraft_types: Aircraft type dictionary
        now_hours: Current time in hours
        
    Returns:
        Fitness score (lower is better)
    """
    total_cost = 0.0
    penalty = 0.0
    
    # Get penalty factors from config
    unfulfilled_penalty = PENALTY_FACTORS["UNFULFILLED_PASSENGERS"]
    overload_penalty = PENALTY_FACTORS["FLIGHT_OVERLOAD"]
    negative_inv_penalty = PENALTY_FACTORS["NEGATIVE_INVENTORY"]
    over_capacity_penalty = PENALTY_FACTORS["OVER_CAPACITY"]
    
    # Find HUB
    hub_code, hub_airport = find_hub(airports)
    
    # Initialize inventory timeline per airport per class
    inventory_timeline = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    
    # Set initial inventory at now_hours
    for airport_code, inv in state.airport_inventories.items():
        for class_type in CLASS_TYPES:
            inventory_timeline[airport_code][class_type][now_hours] = inv.get(class_type, 0)
    
    # Process purchases: available after lead_time + processing_time at HUB
    if hub_code and hub_airport:
        for class_type, qty in individual.purchase_genes.items():
            if qty > 0:
                # Purchase cost from KIT_DEFINITIONS
                kit_cost = KIT_DEFINITIONS[class_type]["cost"]
                total_cost += qty * kit_cost
                
                # Calculate when purchase becomes available
                lead_time = int(KIT_DEFINITIONS[class_type]["lead_time"])
                processing_time = hub_airport.processing_times.get(class_type, 0)
                available_at_hour = now_hours + lead_time + processing_time
                
                # Check storage capacity
                storage_capacity = hub_airport.storage_capacity.get(class_type, 1000)
                current_stock = inventory_timeline[hub_code][class_type].get(available_at_hour, 0)
                if current_stock == 0:
                    current_stock = inventory_timeline[hub_code][class_type].get(now_hours, 0)
                
                overflow = max(0, (current_stock + qty) - storage_capacity)
                if overflow > 0:
                    penalty += overflow * over_capacity_penalty
                
                # Add to inventory at that hour
                inventory_timeline[hub_code][class_type][available_at_hour] += qty
    
    # Track inventory deltas from flight operations
    inventory_deltas = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    
    # Process each flight load
    for flight in flights:
        dep_hours = flight.scheduled_departure.to_hours()
        if dep_hours < now_hours:
            continue
        
        aircraft = aircraft_types.get(flight.aircraft_type)
        if not aircraft:
            continue
        
        origin = flight.origin
        destination = flight.destination
        airport_origin = airports.get(origin)
        airport_dest = airports.get(destination)
        
        if not airport_origin or not airport_dest:
            continue
        
        for class_type in CLASS_TYPES:
            load_qty = individual.genes.get((flight.flight_id, class_type), 0)
            passengers = flight.planned_passengers.get(class_type, 0)
            capacity = aircraft.kit_capacity.get(class_type, 0)
            
            if load_qty > 0:
                # Loading cost (origin airport)
                loading_cost = airport_origin.loading_costs.get(class_type, 0.0)
                total_cost += load_qty * loading_cost
                
                # Processing cost (destination airport)
                processing_cost = airport_dest.processing_costs.get(class_type, 0.0)
                total_cost += load_qty * processing_cost
                
                # Transport cost: weight * distance * fuel_cost * scale
                weight = KIT_DEFINITIONS[class_type]["weight"]
                distance = flight.planned_distance
                fuel_cost = aircraft.fuel_cost_per_km
                transport_cost = load_qty * weight * distance * fuel_cost * TRANSPORT_COST_SCALE
                total_cost += transport_cost
                
                # Deduct from origin inventory at departure
                inventory_deltas[origin][class_type][dep_hours] -= load_qty
                
                # Add to destination after arrival + processing
                arr_hours = flight.scheduled_arrival.to_hours()
                processing_time = airport_dest.processing_times.get(class_type, 0)
                available_at_dest = arr_hours + processing_time
                inventory_deltas[destination][class_type][available_at_dest] += load_qty
            
            # Penalty: unfulfilled passengers
            # Java formula: UNFULFILLED_FACTOR * distance * kitCost * unfulfilled_qty
            unfulfilled = max(0, passengers - load_qty)
            if unfulfilled > 0:
                kit_cost = KIT_DEFINITIONS[class_type]["cost"]
                distance = flight.planned_distance
                penalty += unfulfilled_penalty * distance * kit_cost * unfulfilled
            
            # Penalty: overload (exceeds aircraft capacity)
            # Java formula: OVERLOAD_FACTOR * distance * fuelCost * kitCost * overload
            overload = max(0, load_qty - capacity)
            if overload > 0:
                kit_cost = KIT_DEFINITIONS[class_type]["cost"]
                distance = flight.planned_distance
                fuel_cost = aircraft.fuel_cost_per_km
                penalty += overload_penalty * distance * fuel_cost * kit_cost * overload
    
    # Compute inventory violations at each hour
    all_hours = set()
    for airport_code in inventory_timeline:
        for class_type in inventory_timeline[airport_code]:
            all_hours.update(inventory_timeline[airport_code][class_type].keys())
    for airport_code in inventory_deltas:
        for class_type in inventory_deltas[airport_code]:
            all_hours.update(inventory_deltas[airport_code][class_type].keys())
    
    if all_hours:
        sorted_hours = sorted(all_hours)
        
        for hour in sorted_hours:
            for airport_code in set(list(inventory_timeline.keys()) + list(inventory_deltas.keys())):
                airport = airports.get(airport_code)
                if not airport:
                    continue
                
                for class_type in CLASS_TYPES:
                    # Get current inventory (carry forward)
                    current_inv = None
                    
                    if hour in inventory_timeline[airport_code][class_type]:
                        current_inv = inventory_timeline[airport_code][class_type][hour]
                    else:
                        for h in range(hour - 1, now_hours - 1, -1):
                            if h in inventory_timeline[airport_code][class_type]:
                                current_inv = inventory_timeline[airport_code][class_type][h]
                                break
                        if current_inv is None:
                            current_inv = inventory_timeline[airport_code][class_type].get(now_hours, 0)
                    
                    # Apply delta
                    delta = inventory_deltas[airport_code][class_type].get(hour, 0)
                    new_inv = current_inv + delta
                    
                    # Penalty for negative inventory
                    if new_inv < 0:
                        penalty += abs(new_inv) * negative_inv_penalty
                    
                    # Penalty for over-capacity
                    storage_capacity = airport.storage_capacity.get(class_type, 1000)
                    if new_inv > storage_capacity:
                        overflow = new_inv - storage_capacity
                        penalty += overflow * over_capacity_penalty
                    
                    # Store and propagate
                    inventory_timeline[airport_code][class_type][hour] = new_inv
                    if hour + 1 not in inventory_timeline[airport_code][class_type]:
                        inventory_timeline[airport_code][class_type][hour + 1] = new_inv
    
    return total_cost + penalty

