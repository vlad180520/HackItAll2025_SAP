"""
Conservative Strategy - Only load what we KNOW exists.

Key principles:
1. Start with INITIAL INVENTORY from CSV
2. ONLY DEDUCT when we load (never add back - too risky)
3. Stop loading from airport when stock is LOW (keep buffer)
4. Purchase at HUB proactively
5. Accept some UNFULFILLED (~450$/kit) to avoid NEGATIVE_INVENTORY (5342$/kit)

This strategy is PESSIMISTIC about inventory - it assumes the worst case.
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

# API purchase limits
API_PURCHASE_LIMITS = {
    "FIRST": 42000,
    "BUSINESS": 42000,
    "PREMIUM_ECONOMY": 42000,
    "ECONOMY": 42000,
}

# Safety buffer - keep at least this much stock at each airport
# to account for uncertainty in our tracking
SAFETY_BUFFER = {
    "FIRST": 50,
    "BUSINESS": 100,
    "PREMIUM_ECONOMY": 75,
    "ECONOMY": 200,
}


class ConservativeStrategy:
    """
    Conservative strategy that only loads what we're SURE exists.
    
    Key insight: It's MUCH better to have UNFULFILLED passengers (~450$/kit)
    than NEGATIVE_INVENTORY (5342$/kit) - that's 12x difference!
    
    So we're VERY careful about loading and keep safety buffers.
    """
    
    def __init__(self, config=None):
        self.config = config
        
        # Track inventory pessimistically
        # Only DEDUCT, never ADD (arrivals are too uncertain)
        self.inventory: Dict[str, Dict[str, int]] = {}
        self.hub_code: str = None
        self.initialized = False
        
        # Track flights we've already loaded
        self.loaded_flights: Set[str] = set()
        
        # Track purchases in transit
        self.pending_purchases: Dict[int, Dict[str, int]] = {}  # hour -> {class: amount}
        
        self.round_count = 0
        
        logger.info("ConservativeStrategy initialized")
    
    def _initialize(self, airports: Dict[str, Airport]):
        """Initialize inventory from CSV data."""
        if self.initialized:
            return
        
        for code, airport in airports.items():
            # Start with initial inventory from CSV
            self.inventory[code] = dict(airport.current_inventory)
            
            if airport.is_hub:
                self.hub_code = code
        
        self.initialized = True
        
        hub_stock = self.inventory.get(self.hub_code, {})
        logger.info(f"Initialized with HUB={self.hub_code}, HUB stock: {hub_stock}")
    
    def _process_pending_purchases(self, now_hours: int):
        """Add purchased kits that have arrived."""
        arrived = []
        for arrival_hour, amounts in self.pending_purchases.items():
            if arrival_hour <= now_hours:
                # Purchases arrived at HUB
                for kit_class, amount in amounts.items():
                    current = self.inventory.get(self.hub_code, {}).get(kit_class, 0)
                    self.inventory[self.hub_code][kit_class] = current + amount
                    logger.info(f"Purchase arrived at HUB: +{amount} {kit_class}")
                arrived.append(arrival_hour)
        
        for h in arrived:
            del self.pending_purchases[h]
    
    def _get_safe_available(self, airport_code: str, kit_class: str) -> int:
        """Get safely available stock (with buffer)."""
        current = self.inventory.get(airport_code, {}).get(kit_class, 0)
        buffer = SAFETY_BUFFER.get(kit_class, 100)
        return max(0, current - buffer)
    
    def _consume(self, airport_code: str, kit_class: str, amount: int):
        """Consume kits from inventory."""
        current = self.inventory.get(airport_code, {}).get(kit_class, 0)
        self.inventory[airport_code][kit_class] = current - amount
    
    def record_penalties(self, penalties: List[Dict]) -> None:
        """Log penalties for debugging."""
        for p in penalties:
            if "NEGATIVE_INVENTORY" in p.get("code", ""):
                logger.warning(f"NEGATIVE_INVENTORY: {p.get('reason', '')}")
    
    def optimize(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """Make conservative loading and purchasing decisions."""
        
        self._initialize(airports)
        
        now_hours = state.current_day * 24 + state.current_hour
        
        # Process any arrived purchases
        self._process_pending_purchases(now_hours)
        
        # Get flights departing in next 4 hours
        loading_flights = []
        for f in flights:
            dep_hours = f.scheduled_departure.to_hours()
            if now_hours <= dep_hours < now_hours + 4:
                if f.flight_id not in self.loaded_flights:
                    loading_flights.append(f)
        
        # Sort by departure time
        loading_flights.sort(key=lambda f: f.scheduled_departure.to_hours())
        
        load_decisions = []
        total_loaded = 0
        total_unfulfilled = 0
        
        for flight in loading_flights:
            aircraft = aircraft_types.get(flight.aircraft_type)
            if not aircraft:
                continue
            
            origin = flight.origin
            if origin not in self.inventory:
                continue
            
            kits_to_load = {}
            
            for kit_class in CLASS_TYPES:
                passengers = flight.planned_passengers.get(kit_class, 0)
                if passengers <= 0:
                    continue
                
                aircraft_capacity = aircraft.kit_capacity.get(kit_class, 0)
                safe_available = self._get_safe_available(origin, kit_class)
                
                # Load CONSERVATIVELY: min of what's needed and what's safely available
                load = min(passengers, aircraft_capacity, safe_available)
                
                if load > 0:
                    kits_to_load[kit_class] = load
                    self._consume(origin, kit_class, load)
                    total_loaded += load
                
                unfulfilled = passengers - load
                if unfulfilled > 0:
                    total_unfulfilled += unfulfilled
            
            if kits_to_load:
                load_decisions.append(KitLoadDecision(
                    flight_id=flight.flight_id,
                    kits_per_class=kits_to_load
                ))
                self.loaded_flights.add(flight.flight_id)
        
        # Compute purchases
        purchase_orders = self._compute_purchases(state, airports, now_hours)
        
        self.round_count += 1
        
        # Log every 24 rounds
        if self.round_count % 24 == 0:
            hub_stock = self.inventory.get(self.hub_code, {})
            logger.info(f"Round {self.round_count}: HUB stock: {hub_stock}")
        
        total_purchases = sum(p.kits_per_class.values() for p in purchase_orders) if purchase_orders else 0
        logger.info(f"Conservative: {len(load_decisions)} loads ({total_loaded} kits), "
                   f"{total_unfulfilled} unfulfilled, {total_purchases} purchases")
        
        return load_decisions, purchase_orders
    
    def _compute_purchases(
        self, 
        state: GameState, 
        airports: Dict[str, Airport],
        now_hours: int
    ) -> List[KitPurchaseOrder]:
        """Purchase at HUB when stock gets low."""
        
        if not self.hub_code:
            return []
        
        hub_stock = self.inventory.get(self.hub_code, {})
        hub_airport = airports.get(self.hub_code)
        
        # Thresholds - buy when below these
        thresholds = {
            "FIRST": 500,
            "BUSINESS": 2000,
            "PREMIUM_ECONOMY": 1000,
            "ECONOMY": 8000,
        }
        
        # Targets - buy enough to reach these
        targets = {
            "FIRST": 1500,
            "BUSINESS": 5000,
            "PREMIUM_ECONOMY": 2500,
            "ECONOMY": 20000,
        }
        
        purchase_amounts = {}
        
        for kit_class in CLASS_TYPES:
            current = hub_stock.get(kit_class, 0)
            threshold = thresholds.get(kit_class, 1000)
            target = targets.get(kit_class, 5000)
            
            if current < threshold:
                to_buy = min(target - current, API_PURCHASE_LIMITS.get(kit_class, 42000))
                if to_buy > 0:
                    purchase_amounts[kit_class] = to_buy
                    logger.info(f"PURCHASE {kit_class}: {to_buy} (stock={current} < threshold={threshold})")
        
        if not purchase_amounts:
            return []
        
        # Calculate ETA
        max_lead_time = max(
            int(KIT_DEFINITIONS[ct]["lead_time"])
            for ct in purchase_amounts.keys()
        )
        max_proc = 0
        if hub_airport:
            max_proc = max(
                hub_airport.processing_times.get(ct, 0)
                for ct in purchase_amounts.keys()
            )
        
        eta_hours = now_hours + max_lead_time + max_proc
        
        # Schedule arrival of purchased kits
        if eta_hours not in self.pending_purchases:
            self.pending_purchases[eta_hours] = {}
        for kit_class, amount in purchase_amounts.items():
            current = self.pending_purchases[eta_hours].get(kit_class, 0)
            self.pending_purchases[eta_hours][kit_class] = current + amount
        
        return [KitPurchaseOrder(
            kits_per_class=purchase_amounts,
            order_time=ReferenceHour(day=state.current_day, hour=state.current_hour),
            expected_delivery=ReferenceHour(day=eta_hours // 24, hour=eta_hours % 24)
        )]

