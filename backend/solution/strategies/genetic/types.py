"""Type definitions for genetic algorithm.

Contains Individual class representing a solution candidate (chromosome).
"""

from typing import Dict, Tuple


class Individual:
    """Represents a solution candidate (chromosome).
    
    Attributes:
        genes: Dictionary mapping (flight_id, class) to kit count to load
        purchase_genes: Dictionary mapping class to quantity to purchase at HUB
        fitness: Fitness score (lower is better)
    """
    
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
    
    def __repr__(self) -> str:
        total_load = sum(self.genes.values())
        total_purchase = sum(self.purchase_genes.values())
        return f"Individual(load={total_load}, purch={total_purchase}, fit={self.fitness:.2f})"

