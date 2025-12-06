"""
Integration layer between existing optimizer and new solution system.

Acest fișier face legătura între optimizer-ul vechi și noul sistem modular de soluții.
"""

import logging
from typing import Dict, List, Tuple

from models.game_state import GameState
from models.flight import Flight
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.airport import Airport
from models.aircraft import AircraftType
from config import Config
from solution.config import SolutionConfig
from solution.decision_maker import DecisionMaker

logger = logging.getLogger(__name__)


class SolutionOptimizer:
    """
    Optimizer that uses the modular solution system.
    
    FOLOSEȘTE ACEASTĂ CLASĂ în loc de GreedyOptimizer pentru soluții modulare!
    """
    
    def __init__(self, config: Config, solution_config: SolutionConfig = None):
        """
        Initialize solution optimizer.
        
        Args:
            config: Main configuration (for compatibility)
            solution_config: Solution-specific configuration
        """
        self.config = config
        
        # Create solution config from main config if not provided
        if solution_config is None:
            solution_config = self._convert_config(config)
        
        self.solution_config = solution_config
        self.decision_maker = DecisionMaker(solution_config)
        
        logger.info("SolutionOptimizer initialized with modular solution system")
    
    def _convert_config(self, config: Config) -> SolutionConfig:
        """
        Convert main Config to SolutionConfig.
        
        Args:
            config: Main configuration
            
        Returns:
            Converted solution configuration
        """
        return SolutionConfig(
            SAFETY_BUFFER=config.SAFETY_BUFFER,
            REORDER_THRESHOLD=config.REORDER_THRESHOLD,
            TARGET_STOCK_LEVEL=config.TARGET_STOCK_LEVEL,
            LOOKAHEAD_HOURS=config.LOOKAHEAD_HOURS,
        )
    
    def decide(
        self,
        state: GameState,
        visible_flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft: Dict[str, AircraftType],
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder], str]:
        """
        Produce decisions using the modular solution system.
        
        Args:
            state: Current game state
            visible_flights: List of flights visible at current time
            airports: Dictionary of airports
            aircraft: Dictionary of aircraft types
            
        Returns:
            Tuple of (load_decisions, purchase_orders, rationale)
        """
        logger.info(f"SolutionOptimizer making decisions for round {state.current_round}")
        
        try:
            # Use decision maker to get decisions
            loads, purchases = self.decision_maker.make_decisions(
                state=state,
                flights=visible_flights,
                airports=airports,
                aircraft_types=aircraft,
            )
            
            # Generate rationale
            rationale = (
                f"Greedy strategy: "
                f"{len(loads)} loading decisions, {len(purchases)} purchases"
            )
            
            return loads, purchases, rationale
            
        except Exception as e:
            logger.error(f"Error in SolutionOptimizer: {e}", exc_info=True)
            return [], [], f"Error: {str(e)}"
    
    def update_config(self, **kwargs):
        """
        Update solution configuration parameters.
        
        Args:
            **kwargs: Configuration parameters to update
        """
        for key, value in kwargs.items():
            if hasattr(self.solution_config, key):
                setattr(self.solution_config, key, value)
                logger.info(f"Config updated: {key} = {value}")
        
        # Recreate decision maker with new config
        self.decision_maker.update_config(self.solution_config)
