"""Configuration for genetic algorithm.

Contains hyperparameters and cost scaling factors.
"""

from dataclasses import dataclass


# Transport cost scale factor for fitness calculation
# This scales weight * distance * fuel_cost to reasonable magnitude
TRANSPORT_COST_SCALE = 0.0005


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
    - purchase_horizon_hours: 60 (strategic purchases - 60h lookahead)
    """
    population_size: int = 45
    num_generations: int = 30
    tournament_size: int = 4
    crossover_rate: float = 0.82
    mutation_rate: float = 0.15
    elitism_count: int = 3  # Keep top 3 solutions
    horizon_hours: int = 4  # 4-hour tactical lookahead for loading
    purchase_horizon_hours: int = 60  # 60-hour purchase planning horizon
    no_improvement_limit: int = 8  # Early stop after 8 gens no improvement
    
    # Buffer factors for purchase logic
    purchase_buffer: float = 1.05  # 5% buffer for standard purchases
    purchase_buffer_minimal: float = 1.02  # 2% buffer for minimal variant
    minimal_horizon_hours: int = 36  # Shorter horizon for minimal purchases

