"""Population initialization for genetic algorithm.

Creates diverse initial population with different strategies:
- Conservative: load exactly passengers
- Aggressive: load passengers with class-based buffer
- Random: sample between passengers and passengers*1.1

All variants ensure at least passenger coverage before clamping to availability/capacity.
Flights are processed chronologically with arrivals applied before departures.

IMPORTANT: Purchase computation needs ALL visible flights (not just loading flights)
to properly forecast demand.
"""

import logging
import random
from typing import Dict, List

from models.game_state import GameState
from models.flight import Flight
from models.airport import Airport
from models.aircraft import AircraftType
from config import CLASS_TYPES

from solution.strategies.genetic.types import Individual
from solution.strategies.genetic.config import GeneticConfig
from solution.strategies.genetic.purchases import (
    compute_purchase_genes_simple,
    compute_purchase_genes_minimal,
)
from solution.strategies.genetic.precompute import sort_flights_chronologically

logger = logging.getLogger(__name__)

# Module-level storage for all flights (for purchase computation)
_all_visible_flights: List[Flight] = []


def set_all_visible_flights(flights: List[Flight]):
    """Store all visible flights for purchase computation.
    
    This must be called BEFORE initialize_population with the full flight list,
    not just the filtered loading flights.
    """
    global _all_visible_flights
    _all_visible_flights = flights
    logger.debug(f"Set {len(flights)} all_visible_flights for purchase computation")


def initialize_population(
    ga_config: GeneticConfig,
    state: GameState,
    flights: List[Flight],  # These are loading flights (within horizon)
    airports: Dict[str, Airport],
    aircraft_types: Dict[str, AircraftType],
    now_hours: int,
) -> List[Individual]:
    """Generate initial population with diverse feasible solutions.
    
    Diversity strategy:
    - 30% conservative: minimal costs, exact passenger count
    - 30% aggressive: proactive with buffers
    - 40% random/hybrid: diverse exploration points
    
    All variants bias to loading at least passengers.
    """
    population = []
    
    # Sort flights chronologically for consistent processing
    sorted_flights = sort_flights_chronologically(flights)
    
    conservative_count = int(ga_config.population_size * 0.30)
    aggressive_count = int(ga_config.population_size * 0.30)
    random_count = ga_config.population_size - conservative_count - aggressive_count
    
    # Conservative solutions (minimal cost)
    for _ in range(conservative_count):
        individual = _create_conservative_individual(
            ga_config, state, sorted_flights, airports, aircraft_types, now_hours
        )
        population.append(individual)
    
    # Aggressive solutions (proactive with buffers)
    for _ in range(aggressive_count):
        individual = _create_aggressive_individual(
            ga_config, state, sorted_flights, airports, aircraft_types, now_hours
        )
        population.append(individual)
    
    # Random/hybrid solutions (maximum exploration)
    for _ in range(random_count):
        individual = _create_random_individual(
            ga_config, state, sorted_flights, airports, aircraft_types, now_hours
        )
        population.append(individual)
    
    return population


def _create_conservative_individual(
    ga_config: GeneticConfig,
    state: GameState,
    flights: List[Flight],
    airports: Dict[str, Airport],
    aircraft_types: Dict[str, AircraftType],
    now_hours: int,
) -> Individual:
    """Create conservative solution: load exactly passengers (no buffer).
    
    Conservative approach ensures:
    - Load exactly passenger count (no waste)
    - Minimal purchases (only critical shortages)
    - Flights processed chronologically
    """
    individual = Individual()
    
    # Track inventory changes as we process flights
    inventory_snapshot = _snapshot_inventory(state)
    
    for flight in flights:
        aircraft = aircraft_types.get(flight.aircraft_type)
        if not aircraft:
            continue
        
        origin = flight.origin
        
        for class_type in CLASS_TYPES:
            passengers = flight.planned_passengers.get(class_type, 0)
            capacity = aircraft.kit_capacity.get(class_type, 0)
            available = inventory_snapshot.get(origin, {}).get(class_type, 0)
            
            # Conservative: load exactly passengers
            target = passengers
            load = min(target, capacity, available)
            load = max(load, 0)
            
            individual.genes[(flight.flight_id, class_type)] = load
            
            # Update snapshot
            if origin in inventory_snapshot and class_type in inventory_snapshot[origin]:
                inventory_snapshot[origin][class_type] -= load
    
    # Minimal purchases - use ALL visible flights for demand calculation
    # This is critical: purchase computation needs full flight list, not just loading flights
    all_flights = _all_visible_flights if _all_visible_flights else flights
    individual.purchase_genes = compute_purchase_genes_minimal(
        ga_config, state, all_flights, airports, now_hours
    )
    
    return individual


def _create_aggressive_individual(
    ga_config: GeneticConfig,
    state: GameState,
    flights: List[Flight],
    airports: Dict[str, Airport],
    aircraft_types: Dict[str, AircraftType],
    now_hours: int,
) -> Individual:
    """Create aggressive solution: load with strategic buffer.
    
    Aggressive approach:
    - Load passengers plus class-based buffer (5-10%)
    - More proactive purchases
    - Flights processed chronologically
    """
    individual = Individual()
    
    # Track inventory changes
    inventory_snapshot = _snapshot_inventory(state)
    
    for flight in flights:
        aircraft = aircraft_types.get(flight.aircraft_type)
        if not aircraft:
            continue
        
        origin = flight.origin
        
        for class_type in CLASS_TYPES:
            passengers = flight.planned_passengers.get(class_type, 0)
            capacity = aircraft.kit_capacity.get(class_type, 0)
            available = inventory_snapshot.get(origin, {}).get(class_type, 0)
            
            # Strategic buffer: 5-10% for high-value classes, less for economy
            if class_type == "FIRST":
                buffer_pct = 1.10
            elif class_type == "BUSINESS":
                buffer_pct = 1.08
            elif class_type == "PREMIUM_ECONOMY":
                buffer_pct = 1.05
            else:  # ECONOMY
                buffer_pct = 1.03
            
            # At least passengers, up to buffered amount
            target = int(passengers * buffer_pct)
            target = max(target, passengers)  # Ensure at least passengers
            
            load = min(target, capacity, available)
            load = max(load, 0)
            
            individual.genes[(flight.flight_id, class_type)] = load
            
            # Update snapshot
            if origin in inventory_snapshot and class_type in inventory_snapshot[origin]:
                inventory_snapshot[origin][class_type] -= load
    
    # Proactive purchases - use ALL visible flights for demand calculation
    all_flights = _all_visible_flights if _all_visible_flights else flights
    individual.purchase_genes = compute_purchase_genes_simple(
        ga_config, state, all_flights, airports, now_hours
    )
    
    return individual


def _create_random_individual(
    ga_config: GeneticConfig,
    state: GameState,
    flights: List[Flight],
    airports: Dict[str, Airport],
    aircraft_types: Dict[str, AircraftType],
    now_hours: int,
) -> Individual:
    """Create random feasible solution for exploration.
    
    Random approach:
    - Sample between passengers and passengers*1.1
    - Ensures at least passenger coverage
    - Flights processed chronologically
    """
    individual = Individual()
    
    # Track inventory changes
    inventory_snapshot = _snapshot_inventory(state)
    
    for flight in flights:
        aircraft = aircraft_types.get(flight.aircraft_type)
        if not aircraft:
            continue
        
        origin = flight.origin
        
        for class_type in CLASS_TYPES:
            passengers = flight.planned_passengers.get(class_type, 0)
            capacity = aircraft.kit_capacity.get(class_type, 0)
            available = inventory_snapshot.get(origin, {}).get(class_type, 0)
            
            # Random between passengers (100%) and passengers*1.1 (110%)
            # This ensures at least passenger coverage
            if passengers > 0:
                min_load = passengers  # At least passengers
                max_load = int(passengers * 1.10)  # Up to 10% buffer
                target = random.randint(min_load, max_load)
            else:
                target = 0
            
            load = min(target, capacity, available)
            load = max(load, 0)
            
            individual.genes[(flight.flight_id, class_type)] = load
            
            # Update snapshot
            if origin in inventory_snapshot and class_type in inventory_snapshot[origin]:
                inventory_snapshot[origin][class_type] -= load
    
    # Use ALL visible flights for purchase computation
    all_flights = _all_visible_flights if _all_visible_flights else flights
    individual.purchase_genes = compute_purchase_genes_simple(
        ga_config, state, all_flights, airports, now_hours
    )
    
    return individual


def create_greedy_individual(
    ga_config: GeneticConfig,
    state: GameState,
    flights: List[Flight],
    airports: Dict[str, Airport],
    aircraft_types: Dict[str, AircraftType],
    now_hours: int,
) -> Individual:
    """Create deterministic greedy baseline for injection each generation.
    
    Greedy anchor:
    - Load passengers with small buffer (5-8%)
    - Clamp to availability/capacity
    - Process arrivals chronologically
    - Use buy-when-needed purchase logic
    """
    individual = Individual()
    
    # Sort flights chronologically
    sorted_flights = sort_flights_chronologically(flights)
    
    # Track inventory
    inventory_snapshot = _snapshot_inventory(state)
    
    for flight in sorted_flights:
        aircraft = aircraft_types.get(flight.aircraft_type)
        if not aircraft:
            continue
        
        origin = flight.origin
        
        for class_type in CLASS_TYPES:
            passengers = flight.planned_passengers.get(class_type, 0)
            capacity = aircraft.kit_capacity.get(class_type, 0)
            available = inventory_snapshot.get(origin, {}).get(class_type, 0)
            
            # Greedy: 5-8% buffer, class-dependent
            if class_type == "FIRST":
                buffer_pct = 1.08
            elif class_type == "BUSINESS":
                buffer_pct = 1.06
            elif class_type == "PREMIUM_ECONOMY":
                buffer_pct = 1.05
            else:  # ECONOMY
                buffer_pct = 1.05
            
            target = int(passengers * buffer_pct)
            target = max(target, passengers)  # At least passengers
            
            load = min(target, capacity, available)
            load = max(load, 0)
            
            individual.genes[(flight.flight_id, class_type)] = load
            
            # Update snapshot
            if origin in inventory_snapshot and class_type in inventory_snapshot[origin]:
                inventory_snapshot[origin][class_type] -= load
    
    # Use ALL visible flights for purchase computation (not just loading flights)
    all_flights = _all_visible_flights if _all_visible_flights else flights
    individual.purchase_genes = compute_purchase_genes_simple(
        ga_config, state, all_flights, airports, now_hours
    )
    
    return individual


def _snapshot_inventory(state: GameState) -> Dict[str, Dict[str, int]]:
    """Create a mutable copy of airport inventories."""
    return {
        airport: dict(inv) 
        for airport, inv in state.airport_inventories.items()
    }

