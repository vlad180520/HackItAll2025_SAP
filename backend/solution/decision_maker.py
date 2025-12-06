"""Main decision maker - orchestrates solution strategies."""

import logging
from typing import Dict, List, Tuple

from models.game_state import GameState
from models.flight import Flight
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.airport import Airport
from models.aircraft import AircraftType
from solution.config import SolutionConfig
from solution.strategies.genetic_strategy import GeneticStrategy, GeneticConfig

logger = logging.getLogger(__name__)


class DecisionMaker:
    """Main decision maker - uses Genetic Algorithm strategy."""
    
    def __init__(self, config: SolutionConfig = None):
        if config is None:
            config = SolutionConfig.default()
        
        self.config = config
        
        # Use default GeneticConfig for consistency
        # Parameters optimized for speed/accuracy balance
        ga_config = GeneticConfig()
        
        self.strategy = GeneticStrategy(config=self.config, ga_config=ga_config)
        
        logger.info(
            f"DecisionMaker initialized with GeneticStrategy: "
            f"pop={ga_config.population_size}, gens={ga_config.num_generations}, "
            f"horizon={ga_config.horizon_hours}h"
        )
    
    def make_decisions(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """
        Make all decisions for current round using Genetic Algorithm.
        
        Args:
            state: Current game state
            flights: Upcoming flights
            airports: Airport information
            aircraft_types: Aircraft type information
            
        Returns:
            Tuple of (load_decisions, purchase_orders)
        """
        logger.info(f"Making decisions for day {state.current_day} hour {state.current_hour}")
        
        try:
            loads, purchases = self.strategy.optimize(
                state=state,
                flights=flights,
                airports=airports,
                aircraft_types=aircraft_types,
            )
            
            logger.info(f"Decisions made: {len(loads)} loads, {len(purchases)} purchases")
            return loads, purchases
            
        except Exception as e:
            logger.error(f"Error making decisions: {e}", exc_info=True)
            # Return empty decisions on error
            return [], []
    
    def update_config(self, new_config: SolutionConfig):
        """Update configuration and recreate genetic strategy with optimized parameters."""
        self.config = new_config
        
        ga_config = GeneticConfig(
            population_size=60,
            num_generations=40,
            tournament_size=4,
            crossover_rate=0.85,
            mutation_rate=0.15,
            elitism_count=3,
            horizon_hours=3,
            no_improvement_limit=12
        )
        
        self.strategy = GeneticStrategy(config=new_config, ga_config=ga_config)
        logger.info("Configuration updated, GeneticStrategy recreated with optimized parameters")

