"""Main decision maker - orchestrates solution strategies."""

import logging
from typing import Dict, List, Tuple

from models.game_state import GameState
from models.flight import Flight
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.airport import Airport
from models.aircraft import AircraftType
from solution.config import SolutionConfig
from solution.strategies.final_strategy import FinalStrategy

logger = logging.getLogger(__name__)


class DecisionMaker:
    """Main decision maker - FINAL optimized strategy.
    
    Final strategy:
    - Loads only when movement cost < unfulfilled penalty
    - Minimal purchasing
    - Target: ~1.66B (theoretical minimum)
    """
    
    def __init__(self, config: SolutionConfig = None):
        if config is None:
            config = SolutionConfig.default()
        
        self.config = config
        self.strategy = FinalStrategy(config=self.config)
        
        logger.info("DecisionMaker initialized with FinalStrategy")
    
    def record_penalties(self, penalties: List[Dict]) -> None:
        """Record penalties for strategy adjustment."""
        if hasattr(self.strategy, 'record_penalties'):
            self.strategy.record_penalties(penalties)
    
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
            return [], []
    
    def update_config(self, new_config: SolutionConfig):
        """Update configuration."""
        self.config = new_config
        self.strategy = FinalStrategy(config=new_config)
        logger.info("Configuration updated, FinalStrategy recreated")
