"""
MINIMAL Strategy - Absolute minimum, guaranteed to work.

- Loads NOTHING (0 kits)
- Buys at HUB every round

This GUARANTEES no NEGATIVE_INVENTORY penalties.
UNFULFILLED penalties are 12x cheaper than NEGATIVE_INVENTORY.
"""
import logging
from typing import Dict, List, Tuple

from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.airport import Airport
from models.aircraft import AircraftType
from config import CLASS_TYPES, KIT_DEFINITIONS

logger = logging.getLogger(__name__)


class MinimalStrategy:
    """
    MINIMAL strategy - load nothing, buy regularly.
    
    Expected cost: ~3.8 billion (UNFULFILLED only, no NEGATIVE_INVENTORY)
    """
    
    def __init__(self, config=None):
        self.config = config
        self.round = 0
        self.hub_code = None
        logger.info("=" * 50)
        logger.info("MINIMAL STRATEGY - LOADS NOTHING, BUYS REGULARLY")
        logger.info("=" * 50)
    
    def record_penalties(self, penalties: List[Dict]) -> None:
        """Log negative inventory penalties (should be ZERO)."""
        for p in penalties:
            if "NEGATIVE_INVENTORY" in p.get("code", ""):
                logger.error(f"BUG! NEGATIVE_INVENTORY: {p.get('reason')}")
    
    def optimize(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """Return ZERO loads, regular purchases."""
        
        self.round += 1
        now = state.current_day * 24 + state.current_hour
        
        # Find HUB once
        if self.hub_code is None:
            for code, airport in airports.items():
                if airport.is_hub:
                    self.hub_code = code
                    logger.info(f"Found HUB: {code}")
                    break
        
        # ZERO LOADS - guaranteed no NEGATIVE_INVENTORY
        loads = []
        
        # Purchase every 24 hours
        purchases = []
        if self.round == 1 or self.round % 24 == 0:
            hub = airports.get(self.hub_code)
            
            amounts = {
                "FIRST": 5000,
                "BUSINESS": 20000,
                "PREMIUM_ECONOMY": 10000,
                "ECONOMY": 42000,
            }
            
            # Calculate ETA
            max_lead = 48  # Max lead time
            max_proc = 6   # Max processing
            eta = now + max_lead + max_proc
            
            purchases.append(KitPurchaseOrder(
                kits_per_class=amounts,
                order_time=ReferenceHour(day=state.current_day, hour=state.current_hour),
                expected_delivery=ReferenceHour(day=eta // 24, hour=eta % 24)
            ))
            
            logger.info(f"PURCHASE at round {self.round}: {sum(amounts.values())} kits")
        
        # Log progress
        if self.round % 100 == 0:
            logger.info(f"Round {self.round}: 0 loads, checking purchases...")
        
        return loads, purchases

