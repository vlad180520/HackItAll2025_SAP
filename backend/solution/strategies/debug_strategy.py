"""
DEBUG Strategy - Maximum logging to find the bug.
"""
import logging
from typing import Dict, List, Tuple, Set

from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.airport import Airport
from models.aircraft import AircraftType
from config import CLASS_TYPES, KIT_DEFINITIONS

logger = logging.getLogger(__name__)

# Force logging level
logging.getLogger(__name__).setLevel(logging.INFO)


class DebugStrategy:
    """Debug strategy with maximum logging."""
    
    def __init__(self, config=None):
        self.config = config
        self.round_count = 0
        self.hub_code = None
        self.initial_hub_stock = None
        logger.info("=" * 60)
        logger.info("DEBUG STRATEGY INITIALIZED")
        logger.info("=" * 60)
    
    def record_penalties(self, penalties: List[Dict]) -> None:
        pass
    
    def optimize(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """Make decisions with heavy logging."""
        
        self.round_count += 1
        now_hours = state.current_day * 24 + state.current_hour
        
        # Find HUB and log inventory on first round
        if self.hub_code is None:
            for code, airport in airports.items():
                if airport.is_hub:
                    self.hub_code = code
                    self.initial_hub_stock = dict(airport.current_inventory)
                    logger.info(f"FOUND HUB: {code}")
                    logger.info(f"HUB INITIAL INVENTORY: {airport.current_inventory}")
                    break
            
            if self.hub_code is None:
                logger.error("NO HUB FOUND!")
                return [], []
        
        # Log current state every round
        hub_airport = airports.get(self.hub_code)
        if hub_airport:
            logger.info(f"Round {self.round_count} (Day {state.current_day} Hour {state.current_hour})")
            logger.info(f"  HUB current_inventory: {hub_airport.current_inventory}")
        
        # DON'T LOAD ANYTHING - just return empty loads
        # This should give us ~3.8 billion baseline
        load_decisions = []
        
        # ALWAYS BUY on round 1
        purchase_orders = []
        if self.round_count == 1:
            # Buy immediately!
            purchase_amounts = {
                "FIRST": 10000,
                "BUSINESS": 30000,
                "PREMIUM_ECONOMY": 15000,
                "ECONOMY": 42000,  # Max allowed
            }
            
            # Calculate ETA
            max_lead = max(int(KIT_DEFINITIONS[c]["lead_time"]) for c in purchase_amounts)
            max_proc = max(hub_airport.processing_times.get(c, 0) for c in purchase_amounts) if hub_airport else 6
            eta = now_hours + max_lead + max_proc
            
            logger.info(f"PURCHASING at round 1:")
            logger.info(f"  Amounts: {purchase_amounts}")
            logger.info(f"  Lead time: {max_lead}h, Processing: {max_proc}h, ETA: {eta}h")
            
            purchase_orders.append(KitPurchaseOrder(
                kits_per_class=purchase_amounts,
                order_time=ReferenceHour(day=state.current_day, hour=state.current_hour),
                expected_delivery=ReferenceHour(day=eta // 24, hour=eta % 24)
            ))
        
        # Buy every 48 rounds (2 days)
        elif self.round_count % 48 == 0:
            purchase_amounts = {
                "FIRST": 5000,
                "BUSINESS": 20000,
                "PREMIUM_ECONOMY": 10000,
                "ECONOMY": 42000,
            }
            
            max_lead = max(int(KIT_DEFINITIONS[c]["lead_time"]) for c in purchase_amounts)
            max_proc = max(hub_airport.processing_times.get(c, 0) for c in purchase_amounts) if hub_airport else 6
            eta = now_hours + max_lead + max_proc
            
            logger.info(f"PURCHASING at round {self.round_count}:")
            logger.info(f"  Amounts: {purchase_amounts}")
            
            purchase_orders.append(KitPurchaseOrder(
                kits_per_class=purchase_amounts,
                order_time=ReferenceHour(day=state.current_day, hour=state.current_hour),
                expected_delivery=ReferenceHour(day=eta // 24, hour=eta % 24)
            ))
        
        total_purchases = sum(p.kits_per_class.values() for p in purchase_orders) if purchase_orders else 0
        logger.info(f"  Result: 0 loads, {total_purchases} purchases")
        
        return load_decisions, purchase_orders

