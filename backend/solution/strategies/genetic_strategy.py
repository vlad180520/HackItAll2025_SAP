"""Genetic Algorithm strategy for kit optimization.

Key Design Decisions:
- Horizon: 3 hours (short-term tactical optimization)
- Chromosome: Load genes per (flight_id, class) + purchase genes per class at HUB
- Fitness: Operational costs + penalties from config.PENALTY_FACTORS
- Timeline tracking: Purchases available after lead_time + processing_time
- Inventory flow: Initial stock + arrivals (after processing) + purchases - loads
- Constraint enforcement: Aircraft capacity, inventory availability, storage limits

Important:
- Uses config.KIT_DEFINITIONS for costs, weights, lead times (not hardcoded)
- Uses config.PENALTY_FACTORS for constraint violations
- Purchases at HUB become available after lead_time + processing_time
- Inventory tracked per hour: only available stock counts for flight loads
"""

import logging
import random
from typing import Dict, List, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass

from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.airport import Airport
from models.aircraft import AircraftType
from solution.config import SolutionConfig
from config import CLASS_TYPES, KIT_DEFINITIONS, PENALTY_FACTORS

logger = logging.getLogger(__name__)


@dataclass
class GeneticConfig:
    """Configuration for genetic algorithm.
    
    Optimized for speed and accuracy balance:
    - population_size: 45 (good diversity, faster)
    - num_generations: 30 (sufficient convergence)
    - tournament_size: 4 (balanced selection)
    - crossover_rate: 0.82 (high recombination)
    - mutation_rate: 0.15 (moderate exploration)
    - horizon_hours: 4 (tactical planning)
    - purchase_horizon_hours: 18 (strategic purchases)
    """
    population_size: int = 45
    num_generations: int = 30
    tournament_size: int = 4
    crossover_rate: float = 0.82
    mutation_rate: float = 0.15
    elitism_count: int = 3  # Keep top 3 solutions
    horizon_hours: int = 4  # 4-hour tactical lookahead
    purchase_horizon_hours: int = 18  # 18-hour purchase planning
    no_improvement_limit: int = 8  # Early stop after 8 gens no improvement


class Individual:
    """Represents a solution candidate (chromosome)."""
    
    def __init__(self):
        self.genes: Dict[Tuple[str, str], int] = {}  # (flight_id, class) -> kit_count
        self.purchase_genes: Dict[str, int] = {}  # class -> quantity to purchase at HUB
        self.fitness: float = float('inf')
    
    def copy(self) -> 'Individual':
        """Create a deep copy of this individual."""
        new_ind = Individual()
        new_ind.genes = self.genes.copy()
        new_ind.purchase_genes = self.purchase_genes.copy()
        new_ind.fitness = self.fitness
        return new_ind


class GeneticStrategy:
    """Genetic Algorithm strategy for kit optimization.
    
    Uses penalties and costs from config module (not hardcoded).
    Tracks inventory timeline: purchases available after lead_time + processing_time.
    """
    
    def __init__(self, config: SolutionConfig, ga_config: GeneticConfig = None):
        """Initialize genetic strategy."""
        self.config = config
        self.ga_config = ga_config or GeneticConfig()
        
        logger.info(
            f"GeneticStrategy initialized: pop={self.ga_config.population_size}, "
            f"gens={self.ga_config.num_generations}, horizon={self.ga_config.horizon_hours}h, "
            f"elitism={self.ga_config.elitism_count}, tournament={self.ga_config.tournament_size}"
        )
    
    def optimize(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """Main optimization entry point using genetic algorithm."""
        current_time = ReferenceHour(day=state.current_day, hour=state.current_hour)
        now_hours = current_time.to_hours()
        
        logger.info(f"GA optimizing at {current_time.day}d{current_time.hour}h ({now_hours}h)")
        
        # Filter flights within horizon
        loading_flights = self._get_loading_flights(flights, now_hours)
        logger.info(f"Loading flights: {len(loading_flights)}")
        
        if not loading_flights:
            logger.info("No flights to load, computing purchases only")
            purchases = self._compute_purchases_heuristic(state, flights, airports, now_hours)
            return [], purchases
        
        # Run genetic algorithm
        best_individual = self._run_ga(
            state, loading_flights, airports, aircraft_types, now_hours
        )
        
        # Convert best individual to decisions
        load_decisions = self._individual_to_load_decisions(best_individual)
        purchase_orders = self._individual_to_purchase_orders(best_individual, current_time, airports)
        
        logger.info(
            f"GA completed: {len(load_decisions)} loads, "
            f"{sum(purchase_orders[0].kits_per_class.values()) if purchase_orders else 0} total purchases, "
            f"fitness={best_individual.fitness:.2f}"
        )
        
        return load_decisions, purchase_orders
    
    def _get_loading_flights(self, flights: List[Flight], now_hours: int) -> List[Flight]:
        """Filter flights departing within horizon."""
        horizon_end = now_hours + self.ga_config.horizon_hours
        loading = []
        
        for flight in flights:
            dep_hours = flight.scheduled_departure.to_hours()
            # Only consider flights departing now or very soon (within horizon)
            if now_hours <= dep_hours < horizon_end:
                loading.append(flight)
        
        return loading
    
    def _run_ga(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
        now_hours: int,
    ) -> Individual:
        """Run the genetic algorithm and return the best individual."""
        # Initialize population
        population = self._initialize_population(state, flights, airports, aircraft_types, now_hours)
        
        # Evaluate initial population
        for individual in population:
            individual.fitness = self._evaluate_fitness(
                individual, state, flights, airports, aircraft_types, now_hours
            )
        
        # Sort by fitness (lower is better)
        population.sort(key=lambda ind: ind.fitness)
        best_fitness = population[0].fitness
        generations_no_improvement = 0
        
        logger.info(f"GA Initial: best={best_fitness:.2f}, pop={len(population)}")
        
        # Evolution loop
        for generation in range(self.ga_config.num_generations):
            new_population = []
            
            # Elitism: keep best individuals
            for i in range(self.ga_config.elitism_count):
                new_population.append(population[i].copy())
            
            # Generate offspring
            while len(new_population) < self.ga_config.population_size:
                # Selection
                parent1 = self._tournament_selection(population)
                parent2 = self._tournament_selection(population)
                
                # Crossover
                if random.random() < self.ga_config.crossover_rate:
                    child1, child2 = self._crossover(parent1, parent2)
                else:
                    child1, child2 = parent1.copy(), parent2.copy()
                
                # Mutation
                if random.random() < self.ga_config.mutation_rate:
                    self._mutate(child1, state, flights, airports, aircraft_types)
                if random.random() < self.ga_config.mutation_rate:
                    self._mutate(child2, state, flights, airports, aircraft_types)
                
                # Repair feasibility
                self._repair_individual(child1, state, flights, airports, aircraft_types)
                self._repair_individual(child2, state, flights, airports, aircraft_types)
                
                # Evaluate
                child1.fitness = self._evaluate_fitness(
                    child1, state, flights, airports, aircraft_types, now_hours
                )
                child2.fitness = self._evaluate_fitness(
                    child2, state, flights, airports, aircraft_types, now_hours
                )
                
                new_population.append(child1)
                if len(new_population) < self.ga_config.population_size:
                    new_population.append(child2)
            
            # Replace population
            population = new_population
            population.sort(key=lambda ind: ind.fitness)
            
            # Check for improvement
            current_best = population[0].fitness
            improvement = best_fitness - current_best
            
            if improvement > 0.01:  # Significant improvement (>1 cent)
                best_fitness = current_best
                generations_no_improvement = 0
                # Only log first 3 gens and every 10th for performance
                if generation < 3 or generation % 10 == 0:
                    logger.info(f"Gen {generation+1}: best={best_fitness:.2f} (↓{improvement:.2f})")
            else:
                generations_no_improvement += 1
            
            # Early stopping with relative improvement check
            if generations_no_improvement >= self.ga_config.no_improvement_limit:
                logger.info(
                    f"GA converged at gen {generation+1}: best={population[0].fitness:.2f}"
                )
                break
        
        logger.info(f"GA Final: best={population[0].fitness:.2f} after {generation+1} gens")
        return population[0]
    
    def _initialize_population(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
        now_hours: int,
    ) -> List[Individual]:
        """Generate initial population with diverse feasible solutions.
        
        Improved diversity strategy:
        - 30% conservative: minimal costs, exact passenger count
        - 30% aggressive: proactive with buffers
        - 40% random/hybrid: diverse exploration points
        """
        population = []
        
        conservative_count = int(self.ga_config.population_size * 0.30)
        aggressive_count = int(self.ga_config.population_size * 0.30)
        random_count = self.ga_config.population_size - conservative_count - aggressive_count
        
        # Conservative solutions (minimal cost)
        for _ in range(conservative_count):
            individual = self._create_conservative_individual(
                state, flights, airports, aircraft_types, now_hours
            )
            population.append(individual)
        
        # Aggressive solutions (proactive with buffers)
        for _ in range(aggressive_count):
            individual = self._create_aggressive_individual(
                state, flights, airports, aircraft_types, now_hours
            )
            population.append(individual)
        
        # Random/hybrid solutions (maximum exploration)
        for _ in range(random_count):
            individual = self._create_random_individual(
                state, flights, airports, aircraft_types, now_hours
            )
            population.append(individual)
        
        return population
    
    def _create_conservative_individual(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
        now_hours: int,
    ) -> Individual:
        """Create conservative solution: load exactly passenger count, minimal purchases."""
        individual = Individual()
        
        for flight in flights:
            aircraft = aircraft_types.get(flight.aircraft_type)
            if not aircraft:
                continue
            
            origin_inventory = state.airport_inventories.get(flight.origin, {})
            
            for class_type in CLASS_TYPES:
                passengers = flight.planned_passengers.get(class_type, 0)
                capacity = aircraft.kit_capacity.get(class_type, 0)
                available = origin_inventory.get(class_type, 0)
                
                # Load exactly passengers (no waste)
                load = min(passengers, capacity, available)
                load = max(load, 0)
                
                individual.genes[(flight.flight_id, class_type)] = load
        
        # Minimal purchases - only critical shortages
        individual.purchase_genes = self._compute_purchase_genes_minimal(
            state, flights, airports, now_hours
        )
        
        return individual
    
    def _create_aggressive_individual(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
        now_hours: int,
    ) -> Individual:
        """Create aggressive solution: load with strategic buffer."""
        individual = Individual()
        
        for flight in flights:
            aircraft = aircraft_types.get(flight.aircraft_type)
            if not aircraft:
                continue
            
            origin_inventory = state.airport_inventories.get(flight.origin, {})
            is_hub = airports.get(flight.origin, Airport(
                code=flight.origin, name="", is_hub=False,
                storage_capacity={}, loading_costs={},
                processing_costs={}, processing_times={}
            )).is_hub
            
            for class_type in CLASS_TYPES:
                passengers = flight.planned_passengers.get(class_type, 0)
                capacity = aircraft.kit_capacity.get(class_type, 0)
                available = origin_inventory.get(class_type, 0)
                
                # Strategic buffer: 5-10% for high-value classes, less for economy
                if class_type == "FIRST":
                    buffer_pct = 1.10
                elif class_type == "BUSINESS":
                    buffer_pct = 1.08
                elif class_type == "PREMIUM_ECONOMY":
                    buffer_pct = 1.05
                else:  # ECONOMY
                    buffer_pct = 1.03
                
                load = int(passengers * buffer_pct)
                load = min(load, capacity, available)
                load = max(load, 0)
                
                individual.genes[(flight.flight_id, class_type)] = load
        
        # Proactive purchases
        individual.purchase_genes = self._compute_purchase_genes_simple(
            state, flights, airports, now_hours
        )
        
        return individual
    
    def _create_random_individual(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
        now_hours: int,
    ) -> Individual:
        """Create random feasible solution for exploration."""
        individual = Individual()
        
        for flight in flights:
            aircraft = aircraft_types.get(flight.aircraft_type)
            if not aircraft:
                continue
            
            origin_inventory = state.airport_inventories.get(flight.origin, {})
            
            for class_type in CLASS_TYPES:
                passengers = flight.planned_passengers.get(class_type, 0)
                capacity = aircraft.kit_capacity.get(class_type, 0)
                available = origin_inventory.get(class_type, 0)
                
                # Random between 80% and 110% of passenger count
                if passengers > 0:
                    min_load = int(passengers * 0.8)
                    max_load = int(passengers * 1.1)
                    load = random.randint(min_load, max_load)
                else:
                    load = 0
                
                load = min(load, capacity, available)
                load = max(load, 0)
                
                individual.genes[(flight.flight_id, class_type)] = load
        
        individual.purchase_genes = self._compute_purchase_genes_simple(
            state, flights, airports, now_hours
        )
        
        return individual
    
    def _compute_purchase_genes_simple(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        now_hours: int,
    ) -> Dict[str, int]:
        """Compute smart purchase quantities per class at HUB.
        
        Considers:
        - Lead time + processing time for availability
        - Only purchases that can serve flights within purchase horizon
        - Storage capacity constraints
        """
        purchase_genes = {}
        
        # Find HUB
        hub_code = None
        for code, airport in airports.items():
            if airport.is_hub:
                hub_code = code
                break
        
        if not hub_code:
            return {c: 0 for c in CLASS_TYPES}
        
        hub_inventory = state.airport_inventories.get(hub_code, {})
        hub_airport = airports[hub_code]
        
        # Estimate demand from flights leaving HUB in purchase horizon
        demand_per_class = defaultdict(int)
        horizon_end = now_hours + self.ga_config.purchase_horizon_hours
        
        for flight in flights:
            if flight.origin == hub_code:
                dep_hours = flight.scheduled_departure.to_hours()
                if now_hours <= dep_hours < horizon_end:
                    for class_type in CLASS_TYPES:
                        demand_per_class[class_type] += flight.planned_passengers.get(class_type, 0)
        
        # Purchase decisions considering lead time
        for class_type in CLASS_TYPES:
            stock = hub_inventory.get(class_type, 0)
            demand = demand_per_class[class_type]
            
            # Calculate when purchase would be available
            lead_time = int(KIT_DEFINITIONS[class_type]["lead_time"])
            processing_time = hub_airport.processing_times.get(class_type, 0)
            eta_hours = now_hours + lead_time + processing_time
            
            # Only count demand for flights AFTER purchase arrives
            viable_demand = 0
            for flight in flights:
                if flight.origin == hub_code:
                    dep_hours = flight.scheduled_departure.to_hours()
                    if eta_hours <= dep_hours < horizon_end:
                        viable_demand += flight.planned_passengers.get(class_type, 0)
            
            # Purchase if stock insufficient for viable demand
            threshold = viable_demand * 0.95
            
            if stock < threshold and viable_demand > 0:
                target = int(viable_demand * 1.10)  # 10% buffer
                needed = max(0, target - stock)
                capacity = hub_airport.storage_capacity.get(class_type, 1000)
                
                # Don't exceed storage capacity
                max_purchase = max(0, capacity - stock)
                purchase = min(needed, max_purchase)
                purchase_genes[class_type] = max(0, purchase)
            else:
                purchase_genes[class_type] = 0
        
        return purchase_genes
    
    def _compute_purchase_genes_minimal(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        now_hours: int,
    ) -> Dict[str, int]:
        """Compute minimal purchase quantities - only critical shortages.
        
        Conservative approach considering lead time constraints.
        """
        purchase_genes = {}
        
        # Find HUB
        hub_code = None
        for code, airport in airports.items():
            if airport.is_hub:
                hub_code = code
                break
        
        if not hub_code:
            return {c: 0 for c in CLASS_TYPES}
        
        hub_inventory = state.airport_inventories.get(hub_code, {})
        hub_airport = airports[hub_code]
        
        # Estimate immediate demand (shorter horizon for conservative approach)
        demand_per_class = defaultdict(int)
        horizon_end = now_hours + 12  # 12-hour horizon for minimal approach
        
        for flight in flights:
            if flight.origin == hub_code:
                dep_hours = flight.scheduled_departure.to_hours()
                
                # Calculate ETA for purchases
                lead_time = int(KIT_DEFINITIONS["ECONOMY"]["lead_time"])  # Use economy as baseline
                processing_time = hub_airport.processing_times.get("ECONOMY", 0)
                earliest_eta = now_hours + lead_time + processing_time
                
                # Only count flights we can serve
                if earliest_eta <= dep_hours < horizon_end:
                    for class_type in CLASS_TYPES:
                        demand_per_class[class_type] += flight.planned_passengers.get(class_type, 0)
        
        # Purchase only if critically low
        for class_type in CLASS_TYPES:
            stock = hub_inventory.get(class_type, 0)
            demand = demand_per_class[class_type]
            
            # Only purchase if stock < 70% of viable demand
            if stock < demand * 0.70 and demand > 0:
                needed = int(demand * 0.90) - stock  # Buy just enough
                capacity = hub_airport.storage_capacity.get(class_type, 1000)
                purchase = min(needed, capacity - stock)
                purchase_genes[class_type] = max(0, purchase)
            else:
                purchase_genes[class_type] = 0
        
        return purchase_genes
    
    def _evaluate_fitness(
        self,
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
        - Transport costs (weight × distance × fuel_cost_per_km)
        - Purchase costs (from KIT_DEFINITIONS)
        
        Penalties (from PENALTY_FACTORS):
        - UNFULFILLED_PASSENGERS: passengers not covered by kits
        - FLIGHT_OVERLOAD: kits exceed aircraft capacity
        - NEGATIVE_INVENTORY: inventory goes negative at any point
        
        Timeline:
        - Purchases at HUB available after: now + lead_time + processing_time
        - Only stock available BEFORE flight departure counts for that flight
        """
        total_cost = 0.0
        penalty = 0.0
        
        # Get penalty factors from config
        unfulfilled_penalty = PENALTY_FACTORS["UNFULFILLED_PASSENGERS"]
        overload_penalty = PENALTY_FACTORS["FLIGHT_OVERLOAD"]
        negative_inv_penalty = PENALTY_FACTORS["NEGATIVE_INVENTORY"]
        over_capacity_penalty = PENALTY_FACTORS["OVER_CAPACITY"]
        incorrect_load_penalty = PENALTY_FACTORS.get("INCORRECT_FLIGHT_LOAD", 500.0)
        
        # Find HUB
        hub_code = None
        hub_airport = None
        for code, airport in airports.items():
            if airport.is_hub:
                hub_code = code
                hub_airport = airport
                break
        
        # Initialize inventory timeline per airport per class
        # inventory_timeline[airport][class][hour] = quantity
        # This tracks the ACTUAL stock at each hour (can be 0 or negative)
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
                    
                    # Check if purchase would exceed storage capacity at arrival
                    storage_capacity = hub_airport.storage_capacity.get(class_type, 1000)
                    current_stock = inventory_timeline[hub_code][class_type].get(available_at_hour, 0)
                    if current_stock == 0:
                        current_stock = inventory_timeline[hub_code][class_type].get(now_hours, 0)
                    
                    overflow = max(0, (current_stock + qty) - storage_capacity)
                    if overflow > 0:
                        penalty += overflow * over_capacity_penalty
                    
                    # Add to inventory at that hour (and propagate forward)
                    inventory_timeline[hub_code][class_type][available_at_hour] += qty
        
        # Build flight events sorted by departure time
        flight_events = []
        for flight in flights:
            dep_hours = flight.scheduled_departure.to_hours()
            if dep_hours >= now_hours:  # Only future flights
                flight_events.append((dep_hours, flight))
        flight_events.sort(key=lambda x: x[0])  # Sort only by departure hours
        
        # Track inventory changes per airport/class
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
                    
                    # Transport cost: weight × distance × fuel_cost_per_km
                    weight = KIT_DEFINITIONS[class_type]["weight"]
                    distance = flight.planned_distance
                    fuel_cost = aircraft.fuel_cost_per_km
                    transport_cost = load_qty * weight * distance * fuel_cost
                    total_cost += transport_cost
                    
                    # Deduct from origin inventory at departure time
                    inventory_deltas[origin][class_type][dep_hours] -= load_qty
                    
                    # Add to destination inventory after arrival + processing
                    arr_hours = flight.scheduled_arrival.to_hours()
                    processing_time = airport_dest.processing_times.get(class_type, 0)
                    available_at_dest = arr_hours + processing_time
                    inventory_deltas[destination][class_type][available_at_dest] += load_qty
                
                # Penalty: unfulfilled passengers (CRITICAL - high weight)
                unfulfilled = max(0, passengers - load_qty)
                if unfulfilled > 0:
                    # Progressive penalty: more severe for higher unfulfilled counts
                    if unfulfilled <= 2:
                        penalty += unfulfilled * unfulfilled_penalty * 0.8  # Small shortage - lighter
                    elif unfulfilled <= 5:
                        penalty += unfulfilled * unfulfilled_penalty * 1.0  # Medium shortage
                    else:
                        penalty += unfulfilled * unfulfilled_penalty * 1.5  # Large shortage - severe
                
                # Penalty: overload (exceeds aircraft capacity)
                overload = max(0, load_qty - capacity)
                if overload > 0:
                    # Lighter penalty for small overloads (might be optimization artifact)
                    if overload <= 2:
                        penalty += overload * overload_penalty * 0.5
                    else:
                        penalty += overload * overload_penalty
        
        # Compute inventory at each relevant hour and check for violations
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
                        # Get current inventory (carry forward from last known value)
                        current_inv = None
                        
                        # Try to get exact value at this hour
                        if hour in inventory_timeline[airport_code][class_type]:
                            current_inv = inventory_timeline[airport_code][class_type][hour]
                        else:
                            # Carry forward from most recent hour before this
                            for h in range(hour - 1, now_hours - 1, -1):
                                if h in inventory_timeline[airport_code][class_type]:
                                    current_inv = inventory_timeline[airport_code][class_type][h]
                                    break
                            
                            # If still None, use initial inventory
                            if current_inv is None:
                                current_inv = inventory_timeline[airport_code][class_type].get(now_hours, 0)
                        
                        # Apply delta at this hour
                        delta = inventory_deltas[airport_code][class_type].get(hour, 0)
                        new_inv = current_inv + delta
                        
                        # Penalty for negative inventory (stock shortage)
                        if new_inv < 0:
                            penalty += abs(new_inv) * negative_inv_penalty
                        
                        # Penalty for over-capacity (exceeds storage limit)
                        storage_capacity = airport.storage_capacity.get(class_type, 1000)
                        if new_inv > storage_capacity:
                            overflow = new_inv - storage_capacity
                            penalty += overflow * over_capacity_penalty
                        
                        # Store result and propagate to next hour
                        inventory_timeline[airport_code][class_type][hour] = new_inv
                        if hour + 1 not in inventory_timeline[airport_code][class_type]:
                            inventory_timeline[airport_code][class_type][hour + 1] = new_inv
        
        fitness = total_cost + penalty
        return fitness
    
    def _tournament_selection(self, population: List[Individual]) -> Individual:
        """Select an individual using tournament selection."""
        tournament = random.sample(population, self.ga_config.tournament_size)
        return min(tournament, key=lambda ind: ind.fitness)
    
    def _crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        """Perform two-point crossover with gene preservation.
        
        Improved crossover:
        - Two-point crossover for better gene mixing
        - Preserves good gene clusters from both parents
        """
        child1 = Individual()
        child2 = Individual()
        
        # Convert genes to lists for easier crossover
        gene_keys = list(parent1.genes.keys())
        if not gene_keys:
            return parent1.copy(), parent2.copy()
        
        # Two-point crossover for better diversity
        if len(gene_keys) > 2:
            point1 = random.randint(1, len(gene_keys) - 2)
            point2 = random.randint(point1 + 1, len(gene_keys) - 1)
        else:
            point1 = 1
            point2 = len(gene_keys) - 1
        
        for i, key in enumerate(gene_keys):
            if i < point1 or i >= point2:
                child1.genes[key] = parent1.genes.get(key, 0)
                child2.genes[key] = parent2.genes.get(key, 0)
            else:
                child1.genes[key] = parent2.genes.get(key, 0)
                child2.genes[key] = parent1.genes.get(key, 0)
        
        # Crossover purchase genes (blend approach for better exploration)
        for class_type in CLASS_TYPES:
            p1_val = parent1.purchase_genes.get(class_type, 0)
            p2_val = parent2.purchase_genes.get(class_type, 0)
            
            # 50% chance of each: pure copy, blend, or weighted average
            rand = random.random()
            if rand < 0.33:
                child1.purchase_genes[class_type] = p1_val
                child2.purchase_genes[class_type] = p2_val
            elif rand < 0.66:
                child1.purchase_genes[class_type] = p2_val
                child2.purchase_genes[class_type] = p1_val
            else:
                # Blend: weighted average
                child1.purchase_genes[class_type] = int((p1_val * 0.6 + p2_val * 0.4))
                child2.purchase_genes[class_type] = int((p1_val * 0.4 + p2_val * 0.6))
        
        return child1, child2
    
    def _mutate(
        self,
        individual: Individual,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ):
        """Mutate an individual with adaptive, intelligent perturbations.
        
        Optimized mutation strategies for faster convergence:
        - Fine-tuning (±1) for 60% of mutations (increased from 50%)
        - Medium adjustments (±2 to ±5) for 30% of mutations (reduced from 35%)
        - Large jumps (±10 to ±20) for 10% of mutations (reduced from 15%)
        - Class-aware rates: higher for premium (critical), lower for economy
        """
        # Mutate load genes with adaptive rates
        for key in individual.genes:
            flight_id, class_type = key
            
            # Class-specific mutation rates (premium classes more critical)
            if class_type == "FIRST":
                mut_rate = 0.22  # Reduced from 0.25
            elif class_type == "BUSINESS":
                mut_rate = 0.20  # Reduced from 0.23
            elif class_type == "PREMIUM_ECONOMY":
                mut_rate = 0.17  # Reduced from 0.20
            else:  # ECONOMY
                mut_rate = 0.14  # Reduced from 0.18
            
            if random.random() < mut_rate:
                current = individual.genes[key]
                
                rand = random.random()
                if rand < 0.60:  # Fine-tuning (60%, increased)
                    delta = random.randint(-1, 1)
                elif rand < 0.90:  # Medium adjustment (30%)
                    delta = random.randint(-5, 5)
                else:  # Large jump (10%, reduced)
                    delta = random.randint(-15, 15)  # Reduced range
                
                individual.genes[key] = max(0, current + delta)
        
        # Mutate purchase genes with reduced aggression
        for class_type in individual.purchase_genes:
            if random.random() < 0.20:  # Reduced from 0.25
                current = individual.purchase_genes[class_type]
                
                # Smaller variations for faster convergence
                rand = random.random()
                if rand < 0.50:  # Small adjustment (increased from 40%)
                    delta = random.randint(-8, 8)  # Reduced from ±10
                elif rand < 0.85:  # Medium adjustment
                    delta = random.randint(-25, 25)  # Reduced from ±30
                else:  # Large jump
                    delta = random.randint(-40, 40)  # Reduced from ±50
                
                individual.purchase_genes[class_type] = max(0, current + delta)
    
    def _repair_individual(
        self,
        individual: Individual,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ):
        """Repair an individual to ensure feasibility.
        
        Enforces:
        - Load quantities within aircraft capacity and available inventory
        - Purchase quantities within storage capacity limits
        - No negative inventories after operations
        """
        # Build flight lookup
        flight_dict = {f.flight_id: f for f in flights}
        
        # Track inventory usage per airport
        inventory_usage = defaultdict(lambda: defaultdict(int))
        
        # Repair load genes
        for (flight_id, class_type), load_qty in list(individual.genes.items()):
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
        hub_code = None
        hub_airport = None
        for code, airport in airports.items():
            if airport.is_hub:
                hub_code = code
                hub_airport = airport
                break
        
        if hub_code and hub_airport:
            for class_type in CLASS_TYPES:
                purchase_qty = individual.purchase_genes.get(class_type, 0)
                
                # Storage capacity at HUB
                storage_capacity = hub_airport.storage_capacity.get(class_type, 1000)
                current_stock = state.airport_inventories.get(hub_code, {}).get(class_type, 0)
                
                # Maximum purchase = capacity - current_stock (conservative)
                # This ensures we don't overflow even if no kits are consumed
                max_purchase = max(0, storage_capacity - current_stock)
                
                # Clip purchase to feasible range
                individual.purchase_genes[class_type] = max(0, min(purchase_qty, max_purchase))
    
    def _individual_to_load_decisions(self, individual: Individual) -> List[KitLoadDecision]:
        """Convert individual's load genes to load decisions."""
        decisions_dict = defaultdict(dict)
        
        for (flight_id, class_type), qty in individual.genes.items():
            if qty > 0:
                decisions_dict[flight_id][class_type] = qty
        
        decisions = []
        for flight_id, kits_per_class in decisions_dict.items():
            decisions.append(KitLoadDecision(
                flight_id=flight_id,
                kits_per_class=kits_per_class
            ))
        
        return decisions
    
    def _individual_to_purchase_orders(
        self,
        individual: Individual,
        current_time: ReferenceHour,
        airports: Dict[str, Airport],
    ) -> List[KitPurchaseOrder]:
        """Convert individual's purchase genes to purchase orders.
        
        Calculates expected_delivery based on lead_time + processing_time at HUB.
        Uses actual ETA per class (max across all purchased classes).
        """
        kits_per_class = {k: v for k, v in individual.purchase_genes.items() if v > 0}
        
        if not kits_per_class or sum(kits_per_class.values()) == 0:
            return []
        
        # Find HUB to get processing times
        hub_airport = None
        for airport in airports.values():
            if airport.is_hub:
                hub_airport = airport
                break
        
        if not hub_airport:
            # No HUB found - shouldn't happen, but handle gracefully
            expected_delivery = ReferenceHour(
                day=current_time.day + 1,
                hour=current_time.hour
            )
            return [KitPurchaseOrder(
                kits_per_class=kits_per_class,
                order_time=current_time,
                expected_delivery=expected_delivery
            )]
        
        # Calculate ETA for each class and use the maximum
        # This ensures expected_delivery matches fitness calculation
        max_eta_hours = 0
        for class_type in kits_per_class.keys():
            lead_time = int(KIT_DEFINITIONS[class_type]["lead_time"])
            processing_time = hub_airport.processing_times.get(class_type, 0)
            eta_hours = lead_time + processing_time
            max_eta_hours = max(max_eta_hours, eta_hours)
        
        # Calculate expected delivery time from current time
        current_hours = current_time.to_hours()
        delivery_hours = current_hours + max_eta_hours
        delivery_day = delivery_hours // 24
        delivery_hour = delivery_hours % 24
        
        expected_delivery = ReferenceHour(
            day=delivery_day,
            hour=delivery_hour
        )
        
        return [KitPurchaseOrder(
            kits_per_class=kits_per_class,
            order_time=current_time,
            expected_delivery=expected_delivery
        )]
    
    def _compute_purchases_heuristic(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        now_hours: int,
    ) -> List[KitPurchaseOrder]:
        """Compute purchases using heuristic when no flights to load.
        
        Respects lead_time + processing_time: only purchases that arrive in time.
        """
        hub_code = None
        hub_airport = None
        for code, airport in airports.items():
            if airport.is_hub:
                hub_code = code
                hub_airport = airport
                break
        
        if not hub_code or not hub_airport:
            return []
        
        hub_inventory = state.airport_inventories.get(hub_code, {})
        
        # Estimate demand from upcoming flights (24h horizon)
        demand_per_class = defaultdict(int)
        horizon_end = now_hours + 24
        
        for flight in flights:
            if flight.origin == hub_code:
                dep_hours = flight.scheduled_departure.to_hours()
                if now_hours <= dep_hours < horizon_end:
                    for class_type in CLASS_TYPES:
                        demand_per_class[class_type] += flight.planned_passengers.get(class_type, 0)
        
        # Compute purchases considering ETA
        kits_per_class = {}
        max_eta_hours = 0
        
        for class_type in CLASS_TYPES:
            stock = hub_inventory.get(class_type, 0)
            demand = demand_per_class[class_type]
            
            # Calculate ETA for this class
            lead_time = int(KIT_DEFINITIONS[class_type]["lead_time"])
            processing_time = hub_airport.processing_times.get(class_type, 0)
            eta_hours = now_hours + lead_time + processing_time
            max_eta_hours = max(max_eta_hours, lead_time + processing_time)
            
            # Count viable demand (flights after ETA)
            viable_demand = 0
            for flight in flights:
                if flight.origin == hub_code:
                    dep_hours = flight.scheduled_departure.to_hours()
                    if eta_hours <= dep_hours < horizon_end:
                        viable_demand += flight.planned_passengers.get(class_type, 0)
            
            # Purchase if stock insufficient for viable demand
            if stock < viable_demand * 1.05 and viable_demand > 0:
                target = int(viable_demand * 1.10)
                needed = max(0, target - stock)
                capacity = hub_airport.storage_capacity.get(class_type, 1000)
                purchase = min(needed, capacity - stock)
                if purchase > 0:
                    kits_per_class[class_type] = purchase
        
        if not kits_per_class:
            return []
        
        # Calculate expected delivery using max ETA
        current_time = ReferenceHour(day=state.current_day, hour=state.current_hour)
        delivery_hours = now_hours + max_eta_hours
        delivery_day = delivery_hours // 24
        delivery_hour = delivery_hours % 24
        
        expected_delivery = ReferenceHour(
            day=delivery_day,
            hour=delivery_hour
        )
        
        return [KitPurchaseOrder(
            kits_per_class=kits_per_class,
            order_time=current_time,
            expected_delivery=expected_delivery
        )]
