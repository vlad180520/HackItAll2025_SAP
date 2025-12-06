"""Genetic Algorithm strategy wrapper.

This module provides backward-compatible imports from the modular genetic/ package.

Key Design Decisions:
- Horizon: 4 hours (short-term tactical optimization for loading)
- Purchase horizon: 60 hours (strategic purchase planning)
- Chromosome: Load genes per (flight_id, class) + purchase genes per class at HUB
- Fitness: Operational costs + penalties from config.PENALTY_FACTORS
- Timeline tracking: Purchases available after lead_time + processing_time
- Inventory flow: Initial stock + arrivals (after processing) + purchases - loads
- Constraint enforcement: Aircraft capacity, inventory availability, storage limits
- Greedy anchor: Deterministic baseline injected each generation

Important:
- Uses config.KIT_DEFINITIONS for costs, weights, lead times (not hardcoded)
- Uses config.PENALTY_FACTORS for constraint violations
- Purchases at HUB become available after lead_time + processing_time
- Inventory tracked per hour: only available stock counts for flight loads
- Buy-when-needed logic: purchases based on demand projection, not penalty comparison
"""

# Import from modular structure
from solution.strategies.genetic.config import GeneticConfig, TRANSPORT_COST_SCALE
from solution.strategies.genetic.types import Individual
from solution.strategies.genetic.strategy import GeneticStrategy

__all__ = [
    "GeneticStrategy",
    "GeneticConfig",
    "Individual",
    "TRANSPORT_COST_SCALE",
]
