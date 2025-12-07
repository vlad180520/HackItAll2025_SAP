"""
Zero-Load Strategy - The absolute minimum baseline.

This strategy loads NOTHING and buys NOTHING.

Why? Because:
1. We CANNOT know the real API inventory
2. Our local tracking is ALWAYS wrong
3. Loading causes NEGATIVE_INVENTORY (5342$/kit) when we guess wrong
4. NOT loading causes UNFULFILLED_PASSENGERS (~450$/kit)
5. UNFULFILLED is 12x BETTER than NEGATIVE_INVENTORY

This gives us a BASELINE to compare against.
"""
import logging
from typing import Dict, List, Tuple

from models.game_state import GameState
from models.flight import Flight
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.airport import Airport
from models.aircraft import AircraftType

logger = logging.getLogger(__name__)


class ZeroLoadStrategy:
    """Strategy that does NOTHING - baseline for comparison."""
    
    def __init__(self, config=None):
        self.config = config
        self.round_count = 0
        logger.info("ZeroLoadStrategy initialized - LOADING NOTHING")
    
    def record_penalties(self, penalties: List[Dict]) -> None:
        """Record penalties (no-op for this strategy)."""
        pass
    
    def optimize(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """Return empty decisions - load nothing, buy nothing."""
        
        self.round_count += 1
        
        if self.round_count % 24 == 0:
            logger.info(f"ZeroLoadStrategy: Round {self.round_count} - 0 loads, 0 purchases (BASELINE)")
        
        # Return EMPTY lists - no loads, no purchases
        return [], []

