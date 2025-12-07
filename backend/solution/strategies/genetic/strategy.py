"""Main genetic algorithm strategy for kit optimization.

Key Design Decisions:
- Horizon: 4 hours (short-term tactical optimization)
- Chromosome: Load genes per (flight_id, class) + purchase genes per class at HUB
- Fitness: Operational costs + penalties from config.PENALTY_FACTORS
- Timeline tracking: Purchases available after lead_time + processing_time
- Inventory flow: Initial stock + arrivals (after processing) + purchases - loads
- Constraint enforcement: Aircraft capacity, inventory availability, storage limits
- Greedy anchor: Deterministic baseline injected each generation

Important:
- Uses config.KIT_DEFINITIONS for costs, weights, lead times
- Uses config.PENALTY_FACTORS for constraint violations
- Purchases at HUB become available after lead_time + processing_time
- Inventory tracked per hour: only available stock counts for flight loads
"""

import logging
import random
from typing import Dict, List, Tuple
from collections import defaultdict

from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.airport import Airport
from models.aircraft import AircraftType
from solution.config import SolutionConfig
from config import KIT_DEFINITIONS

from solution.strategies.genetic.config import GeneticConfig
from solution.strategies.genetic.types import Individual
from solution.strategies.genetic.precompute import find_hub
from solution.strategies.genetic.initialization import (
    initialize_population,
    create_greedy_individual,
    set_all_visible_flights,
)
from solution.strategies.genetic.purchases import compute_purchases_heuristic
from solution.strategies.genetic.repair import repair_individual
from solution.strategies.genetic.operators import (
    tournament_selection,
    crossover,
    mutate,
)
from solution.strategies.genetic.fitness import evaluate_fitness
from solution.strategies.genetic.optimizations import (
    precompute_round_data,
    evaluate_fitness_optimized,
    local_search,
    adaptive_mutation_rate,
)

logger = logging.getLogger(__name__)

# Configure file logging for detailed analysis
_file_handler = None

def setup_data_logging():
    """Setup logging to data_response.log for analysis."""
    global _file_handler
    if _file_handler is None:
        _file_handler = logging.FileHandler('data_response.log', mode='a')
        _file_handler.setLevel(logging.DEBUG)
        _file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        # Add to root logger to capture all genetic module logs
        logging.getLogger('solution.strategies.genetic').addHandler(_file_handler)
        logging.getLogger('solution.strategies.genetic').setLevel(logging.DEBUG)
        logger.info("Data logging to data_response.log initialized")


class GeneticStrategy:
    """Genetic Algorithm strategy for kit optimization.
    
    Uses penalties and costs from config module.
    Tracks inventory timeline: purchases available after lead_time + processing_time.
    Injects greedy anchor each generation for stability.
    """
    
    def __init__(self, config: SolutionConfig, ga_config: GeneticConfig = None):
        """Initialize genetic strategy."""
        self.config = config
        self.ga_config = ga_config or GeneticConfig()
        
        logger.info(
            f"GeneticStrategy initialized: pop={self.ga_config.population_size}, "
            f"gens={self.ga_config.num_generations}, horizon={self.ga_config.horizon_hours}h, "
            f"purchase_horizon={self.ga_config.purchase_horizon_hours}h, "
            f"elitism={self.ga_config.elitism_count}, tournament={self.ga_config.tournament_size}"
        )
    
    def optimize(
        self,
        state: GameState,
        flights: List[Flight],  # ALL visible flights
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """Main optimization entry point using genetic algorithm."""
        # Setup file logging
        setup_data_logging()
        
        current_time = ReferenceHour(day=state.current_day, hour=state.current_hour)
        now_hours = current_time.to_hours()
        
        logger.info(f"GA optimizing at {current_time.day}d{current_time.hour}h ({now_hours}h)")
        
        # IMPORTANT: Store all visible flights for purchase computation
        # Purchase logic needs full flight list, not just loading flights
        set_all_visible_flights(flights)
        logger.debug(f"Set {len(flights)} all_visible_flights for purchase demand forecasting")
        
        # Log inventory state at HUB for debugging
        hub_code, hub_airport = find_hub(airports)
        if hub_code:
            hub_inv = state.airport_inventories.get(hub_code, {})
            logger.info(f"HUB {hub_code} inventory: {hub_inv}")
        
        # Filter flights within horizon
        loading_flights = self._get_loading_flights(flights, now_hours)
        logger.info(f"Loading flights: {len(loading_flights)} (within {self.ga_config.horizon_hours}h)")
        
        if not loading_flights:
            logger.info("No flights to load, computing purchases only (heuristic)")
            purchases = compute_purchases_heuristic(
                self.ga_config, state, flights, airports, now_hours
            )
            if purchases:
                logger.info(f"Heuristic purchases: {purchases[0].kits_per_class}")
            return [], purchases
        
        # Run genetic algorithm (pass all flights for purchase computation)
        best_individual = self._run_ga(
            state, loading_flights, flights, airports, aircraft_types, now_hours
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
            if now_hours <= dep_hours < horizon_end:
                loading.append(flight)
        
        return loading
    
    def _run_ga(
        self,
        state: GameState,
        loading_flights: List[Flight],  # Flights within horizon for loading
        all_flights: List[Flight],  # All visible flights for purchase computation
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
        now_hours: int,
    ) -> Individual:
        """Run the genetic algorithm and return the best individual.
        
        Optimizations applied:
        - Precomputed round data (no repeated dict lookups)
        - Optimized fitness evaluation
        - Adaptive mutation rates
        - Local search refinement
        """
        # OPTIMIZATION: Precompute static data once
        precomputed = None
        use_optimized = getattr(self.ga_config, 'use_precomputation', True)
        if use_optimized:
            precomputed = precompute_round_data(loading_flights, airports, aircraft_types)
        
        # Initialize population
        population = initialize_population(
            self.ga_config, state, loading_flights, airports, aircraft_types, now_hours
        )
        
        # Evaluate initial population (use optimized if available)
        for individual in population:
            if precomputed:
                individual.fitness = evaluate_fitness_optimized(
                    individual, state, precomputed, now_hours
                )
            else:
                individual.fitness = evaluate_fitness(
                    individual, state, loading_flights, airports, aircraft_types, now_hours
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
            
            # Inject greedy anchor each generation
            greedy_anchor = create_greedy_individual(
                self.ga_config, state, loading_flights, airports, aircraft_types, now_hours
            )
            repair_individual(greedy_anchor, state, loading_flights, airports, aircraft_types)
            if precomputed:
                greedy_anchor.fitness = evaluate_fitness_optimized(
                    greedy_anchor, state, precomputed, now_hours
                )
            else:
                greedy_anchor.fitness = evaluate_fitness(
                    greedy_anchor, state, loading_flights, airports, aircraft_types, now_hours
                )
            new_population.append(greedy_anchor)
            
            # OPTIMIZATION: Adaptive mutation rate
            current_mutation_rate = self.ga_config.mutation_rate
            if getattr(self.ga_config, 'adaptive_mutation', True):
                current_mutation_rate = adaptive_mutation_rate(
                    self.ga_config.mutation_rate,
                    generations_no_improvement,
                    generation,
                    self.ga_config.num_generations,
                )
            
            # Generate offspring
            while len(new_population) < self.ga_config.population_size:
                # Selection
                parent1 = tournament_selection(population, self.ga_config.tournament_size)
                parent2 = tournament_selection(population, self.ga_config.tournament_size)
                
                # Crossover
                if random.random() < self.ga_config.crossover_rate:
                    child1, child2 = crossover(parent1, parent2)
                else:
                    child1, child2 = parent1.copy(), parent2.copy()
                
                # Mutation (using adaptive rate)
                if random.random() < current_mutation_rate:
                    mutate(child1, state, loading_flights, airports, aircraft_types)
                if random.random() < current_mutation_rate:
                    mutate(child2, state, loading_flights, airports, aircraft_types)
                
                # Repair feasibility
                repair_individual(child1, state, loading_flights, airports, aircraft_types)
                repair_individual(child2, state, loading_flights, airports, aircraft_types)
                
                # Evaluate (use optimized if available)
                if precomputed:
                    child1.fitness = evaluate_fitness_optimized(
                        child1, state, precomputed, now_hours
                    )
                    child2.fitness = evaluate_fitness_optimized(
                        child2, state, precomputed, now_hours
                    )
                else:
                    child1.fitness = evaluate_fitness(
                        child1, state, loading_flights, airports, aircraft_types, now_hours
                    )
                    child2.fitness = evaluate_fitness(
                        child2, state, loading_flights, airports, aircraft_types, now_hours
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
                if generation < 3 or generation % 10 == 0:
                    logger.info(f"Gen {generation+1}: best={best_fitness:.2f} (improved {improvement:.2f})")
            else:
                generations_no_improvement += 1
            
            # Early stopping
            if generations_no_improvement >= self.ga_config.no_improvement_limit:
                logger.info(f"GA converged at gen {generation+1}: best={population[0].fitness:.2f}")
                break
        
        # OPTIMIZATION: Local search refinement on best solution
        best = population[0]
        if getattr(self.ga_config, 'use_local_search', True) and precomputed:
            iterations = getattr(self.ga_config, 'local_search_iterations', 5)
            refined = local_search(best, state, precomputed, now_hours, iterations)
            if refined.fitness < best.fitness:
                logger.info(f"Local search improved: {best.fitness:.2f} -> {refined.fitness:.2f}")
                best = refined
        
        logger.info(f"GA Final: best={best.fitness:.2f} after {generation+1} gens")
        return best
    
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
        
        # Find HUB
        hub_code, hub_airport = find_hub(airports)
        
        if not hub_airport:
            # No HUB - use default delivery
            expected_delivery = ReferenceHour(
                day=current_time.day + 1,
                hour=current_time.hour
            )
            return [KitPurchaseOrder(
                kits_per_class=kits_per_class,
                order_time=current_time,
                expected_delivery=expected_delivery
            )]
        
        # Calculate ETA for each class and use maximum
        max_eta_hours = 0
        for class_type in kits_per_class.keys():
            lead_time = int(KIT_DEFINITIONS[class_type]["lead_time"])
            processing_time = hub_airport.processing_times.get(class_type, 0)
            eta_hours = lead_time + processing_time
            max_eta_hours = max(max_eta_hours, eta_hours)
        
        # Calculate expected delivery
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

