"""
BASELINE Strategy - Absolute minimum possible cost.

- NO loads (all passengers unfulfilled)
- NO purchases (no capacity overflow)

This establishes the TRUE baseline cost:
~720 rounds × ~10 flights × ~200 passengers × ~800$/passenger = ~1.15 billion

Any better strategy must beat this.
"""
import logging
from typing import Dict, List, Tuple

from models.game_state import GameState
from models.flight import Flight
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.airport import Airport
from models.aircraft import AircraftType

logger = logging.getLogger(__name__)


class BaselineStrategy:
    """
    ABSOLUTE BASELINE - does nothing.
    
    Returns:
    - 0 load decisions
    - 0 purchase orders
    
    Expected cost: ONLY UNFULFILLED_PASSENGERS penalties
    """
    
    def __init__(self, config=None):
        self.config = config
        self.round = 0
        logger.info("=" * 60)
        logger.info("BASELINE STRATEGY - ZERO LOADS, ZERO PURCHASES")
        logger.info("Expected: Only UNFULFILLED penalties, no EXCEEDS_CAPACITY")
        logger.info("=" * 60)
    
    def record_penalties(self, penalties: List[Dict]) -> None:
        """Track penalties for debugging."""
        for p in penalties:
            code = p.get("code", "")
            if "EXCEEDS_CAPACITY" in code:
                logger.error(f"BUG! EXCEEDS_CAPACITY should NOT happen: {p}")
            elif "NEGATIVE_INVENTORY" in code:
                logger.error(f"BUG! NEGATIVE_INVENTORY should NOT happen: {p}")
    
    def optimize(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """Return NOTHING - establish true baseline."""
        
        self.round += 1
        
        if self.round % 100 == 0:
            logger.info(f"Baseline round {self.round}: 0 loads, 0 purchases")
        
        # Return absolutely nothing
        return [], []

