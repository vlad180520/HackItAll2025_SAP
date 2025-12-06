"""Main decision maker - orchestrates solution strategies."""

import logging
from typing import Dict, List, Tuple

from models.game_state import GameState
from models.flight import Flight
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.airport import Airport
from models.aircraft import AircraftType
from solution.config import SolutionConfig
from solution.strategies.greedy_strategy import GreedyKitStrategy

logger = logging.getLogger(__name__)


class DecisionMaker:
    """
    Main decision maker that coordinates solution strategy.
    
    Folosește GreedyKitStrategy pentru decizii.
    """
    
    def __init__(self, config: SolutionConfig = None):
        """
        Initialize decision maker.
        
        Args:
            config: Solution configuration (uses default if None)
        """
        if config is None:
            config = SolutionConfig.default()
        
        self.config = config
        self.strategy = GreedyKitStrategy(config)
        
        logger.info("DecisionMaker initialized with GreedyKitStrategy")
    
    def make_decisions(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """
        Make all decisions for current round.
        
        Args:
            state: Current game state
            flights: Upcoming flights
            airports: Airport information
            aircraft_types: Aircraft type information
            
        Returns:
            Tuple of (load_decisions, purchase_orders)
        """
        logger.info(f"Making decisions for round {state.current_round}")
        
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
        """
        Update configuration and recreate strategy.
        
        Args:
            new_config: New configuration
        """
        self.config = new_config
        self.strategy = GreedyKitStrategy(new_config)
        logger.info("Configuration updated, strategy recreated")
