"""Main decision maker - orchestrates solution strategies."""

import logging
from typing import Dict, List, Tuple

from models.game_state import GameState
from models.flight import Flight
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.airport import Airport
from models.aircraft import AircraftType
from solution.config import SolutionConfig
from solution.strategies.rolling_lp_strategy import RollingLPStrategy

logger = logging.getLogger(__name__)


class DecisionMaker:
    """
    Main decision maker that coordinates solution strategy.
    
    Uses RollingLPStrategy - rolling-horizon min-cost flow/MILP optimization.
    Falls back to heuristic if solver not available.
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
        self.strategy = RollingLPStrategy(
            config=config,
            horizon_hours=36,
            solver_timeout_s=2
        )
        
        logger.info("DecisionMaker initialized with RollingLPStrategy")
    
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
            # Return empty decisions on error
            return [], []
    
    def update_config(self, new_config: SolutionConfig):
        """
        Update configuration and recreate strategy.
        
        Args:
            new_config: New configuration
        """
        self.config = new_config
        self.strategy = RollingLPStrategy(
            config=new_config,
            horizon_hours=36,
            solver_timeout_s=2
        )
        logger.info("Configuration updated, strategy recreated")
