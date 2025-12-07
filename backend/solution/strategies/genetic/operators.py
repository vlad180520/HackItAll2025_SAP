"""Genetic operators: selection, crossover, mutation.

Implements the core evolutionary operators for the genetic algorithm.
"""

import random
from typing import Dict, List, Tuple

from models.game_state import GameState
from models.flight import Flight
from models.airport import Airport
from models.aircraft import AircraftType
from config import CLASS_TYPES

from solution.strategies.genetic.types import Individual


def tournament_selection(
    population: List[Individual],
    tournament_size: int,
) -> Individual:
    """Select an individual using tournament selection.
    
    Randomly samples tournament_size individuals and returns the best one.
    Lower fitness is better.
    """
    tournament = random.sample(population, tournament_size)
    return min(tournament, key=lambda ind: ind.fitness)


def crossover(parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
    """Perform two-point crossover with gene preservation.
    
    Two-point crossover provides better gene mixing than single-point
    and preserves good gene clusters from both parents.
    
    Returns:
        Tuple of two child individuals
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
    
    # Crossover purchase genes (blend approach)
    for class_type in CLASS_TYPES:
        p1_val = parent1.purchase_genes.get(class_type, 0)
        p2_val = parent2.purchase_genes.get(class_type, 0)
        
        # 33% each: pure copy from p1, pure copy from p2, or weighted blend
        rand = random.random()
        if rand < 0.33:
            child1.purchase_genes[class_type] = p1_val
            child2.purchase_genes[class_type] = p2_val
        elif rand < 0.66:
            child1.purchase_genes[class_type] = p2_val
            child2.purchase_genes[class_type] = p1_val
        else:
            # Blend: weighted average
            child1.purchase_genes[class_type] = int(p1_val * 0.6 + p2_val * 0.4)
            child2.purchase_genes[class_type] = int(p1_val * 0.4 + p2_val * 0.6)
    
    return child1, child2


def mutate(
    individual: Individual,
    state: GameState,
    flights: List[Flight],
    airports: Dict[str, Airport],
    aircraft_types: Dict[str, AircraftType],
) -> None:
    """Mutate an individual with adaptive, intelligent perturbations.
    
    Mutation strategies:
    - Fine-tuning (+-1) for 60% of mutations
    - Medium adjustments (+-2 to +-5) for 30% of mutations  
    - Large jumps (+-10 to +-15) for 10% of mutations
    - Class-aware rates: higher for premium (critical), lower for economy
    
    Args:
        individual: Individual to mutate (modified in place)
        state: Current game state
        flights: List of flights
        airports: Airport dictionary
        aircraft_types: Aircraft type dictionary
    """
    # Mutate load genes with adaptive rates
    for key in individual.genes:
        flight_id, class_type = key
        
        # Class-specific mutation rates (premium classes more critical)
        if class_type == "FIRST":
            mut_rate = 0.22
        elif class_type == "BUSINESS":
            mut_rate = 0.20
        elif class_type == "PREMIUM_ECONOMY":
            mut_rate = 0.17
        else:  # ECONOMY
            mut_rate = 0.14
        
        if random.random() < mut_rate:
            current = individual.genes[key]
            
            rand = random.random()
            if rand < 0.60:  # Fine-tuning (60%)
                delta = random.randint(-1, 1)
            elif rand < 0.90:  # Medium adjustment (30%)
                delta = random.randint(-5, 5)
            else:  # Large jump (10%)
                delta = random.randint(-15, 15)
            
            individual.genes[key] = max(0, current + delta)
    
    # Mutate purchase genes with controlled aggression
    for class_type in individual.purchase_genes:
        if random.random() < 0.20:
            current = individual.purchase_genes[class_type]
            
            rand = random.random()
            if rand < 0.50:  # Small adjustment (50%)
                delta = random.randint(-8, 8)
            elif rand < 0.85:  # Medium adjustment (35%)
                delta = random.randint(-25, 25)
            else:  # Large jump (15%)
                delta = random.randint(-40, 40)
            
            individual.purchase_genes[class_type] = max(0, current + delta)

