"""
Inventory-Aware Strategy for Flight Rotables Optimization.

KEY INSIGHTS from problem analysis:
1. Processing Time > Turnaround Time → kits from outbound flights aren't ready for return flights
2. NEGATIVE_INVENTORY penalty (5342/kit) >> UNFULFILLED_PASSENGERS penalty (~450/kit)
3. BETTER to leave passengers without kits than to go negative inventory!

Strategy:
- Track inventory at each airport using INITIAL STOCK from CSV
- On return flights: load min(passengers, available_stock) 
- Never cause negative inventory
- Purchase at HUB to replenish the system
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.airport import Airport
from models.aircraft import AircraftType
from config import CLASS_TYPES, KIT_DEFINITIONS

logger = logging.getLogger(__name__)

# API Purchase Limits
API_PURCHASE_LIMITS = {
    "FIRST": 42000,
    "BUSINESS": 42000,
    "PREMIUM_ECONOMY": 42000,
    "ECONOMY": 42000,
}


@dataclass 
class AirportInventory:
    """Track inventory at an airport."""
    code: str
    is_hub: bool
    # Current available stock (starts from initial stock)
    stock: Dict[str, int] = field(default_factory=dict)
    # Processing times at this airport
    processing_times: Dict[str, int] = field(default_factory=dict)
    # Capacity limits
    capacity: Dict[str, int] = field(default_factory=dict)
    
    def available(self, kit_class: str) -> int:
        """Get available stock for a class."""
        return max(0, self.stock.get(kit_class, 0))
    
    def consume(self, kit_class: str, amount: int):
        """Consume kits from stock."""
        current = self.stock.get(kit_class, 0)
        self.stock[kit_class] = current - amount
        
    def add(self, kit_class: str, amount: int):
        """Add kits to stock (from arrivals or purchases)."""
        current = self.stock.get(kit_class, 0)
        cap = self.capacity.get(kit_class, 999999)
        self.stock[kit_class] = min(current + amount, cap)


class InventoryAwareStrategy:
    """
    Strategy that tracks inventory and never causes negative stock.
    
    Key principles:
    1. Load min(passengers, available) - never more than available
    2. Initialize inventory from airport's current_inventory (initial stock)
    3. Track our loads (subtract from origin)
    4. Track arrivals (add to destination after processing time)
    5. Purchase at HUB proactively to keep system flowing
    """
    
    def __init__(self, config=None):
        self.config = config
        self.inventory: Dict[str, AirportInventory] = {}
        self.hub_code: Optional[str] = None
        self.initialized = False
        self.round_count = 0
        
        # Track pending arrivals (kit deliveries in transit)
        # {total_hours: {airport: {class: amount}}}
        self.pending_arrivals: Dict[int, Dict[str, Dict[str, int]]] = {}
        
        # Track what we've loaded (to avoid double-loading)
        self.flights_loaded: set = set()
        
        # Track penalties for reactive adjustments
        self.negative_inventory_history: Dict[str, Dict[str, int]] = {}
        
    def _initialize_inventory(self, airports: Dict[str, Airport]):
        """Initialize inventory from airport data (initial stock from CSV)."""
        if self.initialized:
            return
            
        for code, airport in airports.items():
            inv = AirportInventory(
                code=code,
                is_hub=airport.is_hub,
                stock=dict(airport.current_inventory),  # Copy initial stock
                processing_times=dict(airport.processing_times),
                capacity=dict(airport.storage_capacity),
            )
            self.inventory[code] = inv
            
            if airport.is_hub:
                self.hub_code = code
                
        self.initialized = True
        logger.info(f"Initialized inventory for {len(self.inventory)} airports, HUB={self.hub_code}")
        
        # Log initial HUB stock
        if self.hub_code:
            hub = self.inventory[self.hub_code]
            logger.info(f"HUB initial stock: {hub.stock}")

    def _process_pending_arrivals(self, now_hours: int):
        """Process any kit arrivals that should have arrived by now."""
        keys_to_remove = []
        for arrival_hour, arrivals in self.pending_arrivals.items():
            if arrival_hour <= now_hours:
                # These kits have arrived and been processed
                for airport_code, class_amounts in arrivals.items():
                    if airport_code in self.inventory:
                        for kit_class, amount in class_amounts.items():
                            self.inventory[airport_code].add(kit_class, amount)
                            logger.debug(f"Kits arrived: {airport_code} +{amount} {kit_class}")
                keys_to_remove.append(arrival_hour)
                
        for key in keys_to_remove:
            del self.pending_arrivals[key]

    def _schedule_arrival(self, airport_code: str, arrival_hours: int, 
                         kit_class: str, amount: int):
        """Schedule kits to arrive at an airport after processing."""
        if airport_code not in self.inventory:
            return
            
        # Add processing time
        proc_time = self.inventory[airport_code].processing_times.get(kit_class, 5)
        available_hour = arrival_hours + proc_time
        
        if available_hour not in self.pending_arrivals:
            self.pending_arrivals[available_hour] = {}
        if airport_code not in self.pending_arrivals[available_hour]:
            self.pending_arrivals[available_hour][airport_code] = {}
        
        current = self.pending_arrivals[available_hour][airport_code].get(kit_class, 0)
        self.pending_arrivals[available_hour][airport_code][kit_class] = current + amount

    def record_penalties(self, penalties: List[Dict]) -> None:
        """Record penalties for adjusting estimates."""
        for penalty in penalties:
            code = penalty.get("code", "")
            if "NEGATIVE_INVENTORY" in code:
                reason = penalty.get("reason", "")
                # Parse reason to get airport and class
                logger.warning(f"NEGATIVE_INVENTORY penalty: {reason}")
                # Could parse and adjust estimates here

    def optimize(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """Optimize kit loading with inventory awareness."""
        
        self._initialize_inventory(airports)
        
        current_day = state.current_day
        current_hour = state.current_hour
        now_hours = current_day * 24 + current_hour
        
        # Process any pending arrivals
        self._process_pending_arrivals(now_hours)
        
        # Filter flights to load (departing within 4 hours that we haven't loaded yet)
        loading_flights = []
        for f in flights:
            dep_hours = f.scheduled_departure.to_hours()
            if now_hours <= dep_hours < now_hours + 4 and f.flight_id not in self.flights_loaded:
                loading_flights.append(f)
        
        load_decisions = []
        total_loaded = {c: 0 for c in CLASS_TYPES}
        total_unfulfilled = {c: 0 for c in CLASS_TYPES}
        
        # Sort flights by departure time
        loading_flights.sort(key=lambda f: f.scheduled_departure.to_hours())
        
        for flight in loading_flights:
            aircraft = aircraft_types.get(flight.aircraft_type)
            if not aircraft:
                logger.warning(f"Unknown aircraft type: {flight.aircraft_type}")
                continue
                
            origin = flight.origin
            if origin not in self.inventory:
                logger.warning(f"Unknown origin airport: {origin}")
                continue
                
            inv = self.inventory[origin]
            kits_to_load = {}
            
            # Determine if outbound (HUB→outstation) or inbound (outstation→HUB)
            is_outbound = (origin == self.hub_code)
            
            for kit_class in CLASS_TYPES:
                passengers = flight.planned_passengers.get(kit_class, 0)
                if passengers <= 0:
                    continue
                    
                aircraft_capacity = aircraft.kit_capacity.get(kit_class, 0)
                available = inv.available(kit_class)
                
                if is_outbound:
                    # OUTBOUND (HUB→outstation): Load passengers + some extra to replenish
                    # But cap by available stock
                    target = int(passengers * 1.2)  # 20% extra for outstation buffer
                    load = min(target, available, aircraft_capacity)
                else:
                    # INBOUND (outstation→HUB): Load ONLY what's available
                    # Better to have unfulfilled passengers than negative inventory!
                    load = min(passengers, available, aircraft_capacity)
                
                if load > 0:
                    kits_to_load[kit_class] = load
                    total_loaded[kit_class] += load
                    
                unfulfilled = passengers - load
                if unfulfilled > 0:
                    total_unfulfilled[kit_class] += unfulfilled
                    if not is_outbound:
                        logger.debug(f"Flight {flight.flight_number}: {origin} {kit_class} "
                                    f"unfulfilled={unfulfilled} (avail={available}, need={passengers})")
            
            if kits_to_load:
                # Consume from origin inventory
                for kit_class, amount in kits_to_load.items():
                    inv.consume(kit_class, amount)
                    
                    # Schedule arrival at destination after flight + processing
                    arr_hours = flight.scheduled_arrival.to_hours()
                    self._schedule_arrival(flight.destination, arr_hours, kit_class, amount)
                
                load_decisions.append(KitLoadDecision(
                    flight_id=flight.flight_id,
                    kits_per_class=kits_to_load
                ))
                self.flights_loaded.add(flight.flight_id)
        
        # Log inventory status at critical airports
        if self.hub_code and self.round_count % 10 == 0:
            hub_inv = self.inventory[self.hub_code]
            logger.info(f"HUB stock: {hub_inv.stock}")
        
        # Log unfulfilled passengers (these are INTENTIONAL to avoid negative inventory)
        if any(v > 0 for v in total_unfulfilled.values()):
            logger.info(f"INTENTIONAL unfulfilled (avoiding neg inventory): {total_unfulfilled}")
        
        # Purchase decisions
        purchase_orders = self._compute_purchases(state, airports, now_hours)
        
        self.round_count += 1
        
        total_purchases = sum(p.kits_per_class.values() for p in purchase_orders) if purchase_orders else 0
        logger.info(f"InventoryAware Round {self.round_count}: {len(load_decisions)} loads, "
                   f"{total_purchases} purchases")
        
        return load_decisions, purchase_orders
    
    def _compute_purchases(self, state: GameState, airports: Dict[str, Airport], 
                          now_hours: int) -> List[KitPurchaseOrder]:
        """Compute purchase orders at HUB based on stock levels."""
        if not self.hub_code:
            return []
            
        hub = self.inventory[self.hub_code]
        purchase_amounts = {}
        
        # Purchase when stock drops below threshold
        # Thresholds based on expected daily demand
        thresholds = {
            "FIRST": 400,       # ~27/hour × 15 hours buffer
            "BUSINESS": 1500,   # ~100/hour × 15 hours buffer  
            "PREMIUM_ECONOMY": 800,  # ~50/hour × 16 hours buffer
            "ECONOMY": 8000,    # ~500/hour × 16 hours buffer
        }
        
        # Target levels after purchase
        targets = {
            "FIRST": 1500,
            "BUSINESS": 5000,
            "PREMIUM_ECONOMY": 2500,
            "ECONOMY": 20000,
        }
        
        for kit_class in CLASS_TYPES:
            current_stock = hub.available(kit_class)
            threshold = thresholds.get(kit_class, 1000)
            target = targets.get(kit_class, 5000)
            
            if current_stock < threshold:
                # Buy enough to reach target, capped by API limits
                to_buy = min(target - current_stock, API_PURCHASE_LIMITS.get(kit_class, 42000))
                if to_buy > 0:
                    purchase_amounts[kit_class] = to_buy
                    logger.info(f"PURCHASE {kit_class}: {to_buy} (stock={current_stock} < threshold={threshold})")
        
        if not purchase_amounts:
            return []
        
        # Calculate delivery time (lead time + processing time)
        hub_airport = airports.get(self.hub_code)
        max_lead_time = max(
            int(KIT_DEFINITIONS[ct]["lead_time"])
            for ct in purchase_amounts.keys()
        )
        max_processing = 0
        if hub_airport:
            max_processing = max(
                hub_airport.processing_times.get(ct, 0)
                for ct in purchase_amounts.keys()
            )
        
        eta_hours = now_hours + max_lead_time + max_processing
        
        # Schedule the arrival of purchased kits
        for kit_class, amount in purchase_amounts.items():
            self._schedule_arrival(self.hub_code, eta_hours - max_processing, kit_class, amount)
        
        return [KitPurchaseOrder(
            kits_per_class=purchase_amounts,
            order_time=ReferenceHour(day=state.current_day, hour=state.current_hour),
            expected_delivery=ReferenceHour(day=eta_hours // 24, hour=eta_hours % 24)
        )]
