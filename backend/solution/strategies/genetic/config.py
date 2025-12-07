"""Configuration for genetic algorithm.

Contains hyperparameters and cost scaling factors.
Tuned for the actual KitType lead times from Java:
- FIRST: 48h lead time
- BUSINESS: 36h lead time
- PREMIUM_ECONOMY: 24h lead time
- ECONOMY: 12h lead time

## OPTIMIZATION NOTES:

Speed vs Accuracy tradeoff:
- FAST: pop=30, gens=20 (~600 evals) - for many flights/low time
- BALANCED: pop=50, gens=35 (~1750 evals) - default
- ACCURATE: pop=80, gens=60 (~4800 evals) - for final scoring

Key bottlenecks:
- Fitness evaluation (O(flights × classes)) - use precomputation
- Inventory tracking (O(hours)) - use lazy delta tracking  
- Selection/Crossover/Mutation - already O(1)
"""

from dataclasses import dataclass


# Transport cost scale factor for fitness calculation
# This scales weight * distance * fuel_cost to reasonable magnitude
TRANSPORT_COST_SCALE = 0.0005


@dataclass
class GeneticConfig:
    """Configuration for genetic algorithm.
    
    Optimized for speed and accuracy balance:
    - population_size: 40 (reduced from 50 - faster, still diverse)
    - num_generations: 30 (reduced from 35 - faster convergence)
    - tournament_size: 4 (balanced selection pressure)
    - crossover_rate: 0.85 (increased - more exploration)
    - mutation_rate: 0.12 (reduced - less random noise)
    - horizon_hours: 4 (tactical planning window)
    - purchase_horizon_hours: 72 (covers FIRST 48h + processing)
    
    Key insight: FIRST class has 48h lead time, so purchases need 72h+ horizon
    to be useful for flights departing after the purchase arrives.
    """
    # Core GA parameters (OPTIMIZED)
    population_size: int = 40  # Reduced: 20% faster, minimal accuracy loss
    num_generations: int = 30  # Reduced: earlier termination typical
    tournament_size: int = 4   # Balanced selection pressure
    crossover_rate: float = 0.85  # Higher: more exploration
    mutation_rate: float = 0.12   # Lower: less random noise
    elitism_count: int = 3     # Keep top 3 solutions
    
    # Early stopping (AGGRESSIVE)
    no_improvement_limit: int = 8  # Reduced from 10: faster convergence detection
    
    # Time horizons
    horizon_hours: int = 4     # 4-hour tactical lookahead for loading
    purchase_horizon_hours: int = 72  # 72h > 48h (FIRST lead time) + processing
    minimal_horizon_hours: int = 48   # At least cover BUSINESS lead time (36h)
    
    # Buffer factors for purchase logic
    purchase_buffer: float = 1.05      # 5% buffer for standard purchases
    purchase_buffer_minimal: float = 1.02  # 2% buffer for minimal variant
    
    # Optimization flags
    use_precomputation: bool = True   # Use precomputed round data
    use_local_search: bool = True     # Apply local search to best solution
    local_search_iterations: int = 5  # Max local search iterations
    adaptive_mutation: bool = True    # Use adaptive mutation rates


# Alternative configs for different scenarios
FAST_CONFIG = GeneticConfig(
    population_size=25,
    num_generations=15,
    no_improvement_limit=4,
    use_local_search=False,
)

ACCURATE_CONFIG = GeneticConfig(
    population_size=60,
    num_generations=50,
    no_improvement_limit=12,
    use_local_search=True,
    local_search_iterations=10,
)

