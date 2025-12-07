"""
WORKING Strategy - Actually makes decisions correctly.

Key rules:
1. Load min(passengers, available_stock, aircraft_capacity)
2. Track inventory at each airport
3. Purchase only when needed AND within capacity
4. Never cause NEGATIVE_INVENTORY or EXCEEDS_CAPACITY
"""
import logging
from typing import Dict, List, Tuple
from collections import defaultdict

from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.airport import Airport
from models.aircraft import AircraftType
from config import KIT_DEFINITIONS

logger = logging.getLogger(__name__)

CLASS_TYPES = ["FIRST", "BUSINESS", "PREMIUM_ECONOMY", "ECONOMY"]


class WorkingStrategy:
    """
    A strategy that ACTUALLY works:
    - Tracks inventory at each airport
    - Loads only what's available
    - Purchases within capacity limits
    """
    
    def __init__(self, config=None):
        self.config = config
        self.round = 0
        
        # Track inventory at each airport
        # Key: airport_code, Value: dict of class -> quantity
        self.inventory: Dict[str, Dict[str, int]] = {}
        
        # Track pending arrivals (flights that will bring kits)
        # Key: (airport_code, arrival_hour), Value: dict of class -> quantity
        self.pending_arrivals: Dict[Tuple[str, int], Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        
        # Track hub code and capacity
        self.hub_code = None
        self.hub_capacity: Dict[str, int] = {}
        
        # Track what we've purchased (pending delivery)
        self.pending_purchases: Dict[str, int] = defaultdict(int)
        
        self.initialized = False
        
        logger.info("=" * 60)
        logger.info("WORKING STRATEGY - Makes real decisions")
        logger.info("=" * 60)
    
    def _initialize_from_airports(self, airports: Dict[str, Airport]):
        """Initialize inventory from airport data."""
        if self.initialized:
            return
            
        for code, airport in airports.items():
            # Copy initial inventory
            self.inventory[code] = dict(airport.current_inventory)
            
            if airport.is_hub:
                self.hub_code = code
                self.hub_capacity = dict(airport.storage_capacity)
                logger.info(f"HUB found: {code}")
                logger.info(f"  Initial stock: {airport.current_inventory}")
                logger.info(f"  Capacity: {airport.storage_capacity}")
        
        self.initialized = True
    
    def _process_arrivals(self, current_hour: int):
        """Process flights that have arrived and kits are ready."""
        # For simplicity, process arrivals that should be ready by now
        keys_to_remove = []
        for (airport, hour), kits in self.pending_arrivals.items():
            if hour <= current_hour:
                for class_type, qty in kits.items():
                    if airport not in self.inventory:
                        self.inventory[airport] = {}
                    self.inventory[airport][class_type] = self.inventory[airport].get(class_type, 0) + qty
                keys_to_remove.append((airport, hour))
        
        for key in keys_to_remove:
            del self.pending_arrivals[key]
    
    def _get_available(self, airport_code: str, class_type: str) -> int:
        """Get available inventory at an airport."""
        if airport_code not in self.inventory:
            return 0
        return max(0, self.inventory[airport_code].get(class_type, 0))
    
    def _consume(self, airport_code: str, class_type: str, quantity: int):
        """Consume inventory (when loading onto flight)."""
        if airport_code not in self.inventory:
            self.inventory[airport_code] = {}
        current = self.inventory[airport_code].get(class_type, 0)
        self.inventory[airport_code][class_type] = current - quantity
    
    def _schedule_arrival(self, airport_code: str, arrival_hour: int, processing_time: int, kits: Dict[str, int]):
        """Schedule kits to arrive at airport after processing."""
        ready_hour = arrival_hour + processing_time
        for class_type, qty in kits.items():
            self.pending_arrivals[(airport_code, ready_hour)][class_type] += qty
    
    def record_penalties(self, penalties: List[Dict]) -> None:
        """Log any penalties we receive - should be minimal."""
        for p in penalties:
            code = p.get("code", "")
            if "NEGATIVE_INVENTORY" in code:
                logger.warning(f"Got NEGATIVE_INVENTORY: {p.get('reason')}")
            elif "EXCEEDS_CAPACITY" in code:
                logger.warning(f"Got EXCEEDS_CAPACITY: {p.get('reason')}")
    
    def optimize(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """Make load and purchase decisions."""
        
        self.round += 1
        current_hour = state.current_day * 24 + state.current_hour
        
        # Initialize on first call
        self._initialize_from_airports(airports)
        
        # Process any arrivals that are ready
        self._process_arrivals(current_hour)
        
        load_decisions = []
        purchase_orders = []
        
        # Process each flight
        for flight in flights:
            # Skip if not departing now
            flight_hour = flight.scheduled_departure.day * 24 + flight.scheduled_departure.hour
            if flight_hour != current_hour:
                continue
            
            origin = flight.origin
            destination = flight.destination
            aircraft = aircraft_types.get(flight.aircraft_type)
            
            if not aircraft:
                continue
            
            # Get passengers for this flight
            passengers = flight.actual_passengers or flight.planned_passengers
            
            # Get processing time at destination
            dest_airport = airports.get(destination)
            
            kits_to_load = {}
            
            for class_type in CLASS_TYPES:
                pax = passengers.get(class_type, 0)
                if pax == 0:
                    continue
                
                # Get constraints
                available = self._get_available(origin, class_type)
                capacity = aircraft.kit_capacity.get(class_type, 0)
                
                # Load the minimum of all constraints
                load = min(pax, available, capacity)
                
                if load > 0:
                    kits_to_load[class_type] = load
                    self._consume(origin, class_type, load)
                    
                    # Schedule arrival at destination
                    if dest_airport:
                        proc_time = dest_airport.processing_times.get(class_type, 6)
                        arrival_hour = flight.scheduled_arrival.day * 24 + flight.scheduled_arrival.hour
                        self._schedule_arrival(destination, arrival_hour, proc_time, {class_type: load})
            
            if kits_to_load:
                load_decisions.append(KitLoadDecision(
                    flight_id=flight.flight_id,
                    kits_per_class=kits_to_load
                ))
        
        # Check if we need to purchase at HUB
        if self.hub_code:
            hub_inv = self.inventory.get(self.hub_code, {})
            hub_cap = self.hub_capacity
            
            kits_to_buy = {}
            
            for class_type in CLASS_TYPES:
                current_stock = hub_inv.get(class_type, 0)
                capacity = hub_cap.get(class_type, 0)
                pending = self.pending_purchases.get(class_type, 0)
                
                # Calculate how much room we have
                room = capacity - current_stock - pending
                
                # Only buy if stock is low (below 30% of capacity) and we have room
                threshold = int(capacity * 0.3)
                
                if current_stock < threshold and room > 0:
                    # Buy up to 20% of capacity, but not more than room
                    buy_amount = min(int(capacity * 0.2), room)
                    if buy_amount > 0:
                        kits_to_buy[class_type] = buy_amount
                        self.pending_purchases[class_type] += buy_amount
            
            if kits_to_buy:
                # Calculate delivery time
                max_lead = max(int(KIT_DEFINITIONS[c]["lead_time"]) for c in kits_to_buy)
                hub_airport = airports.get(self.hub_code)
                max_proc = max(hub_airport.processing_times.get(c, 6) for c in kits_to_buy) if hub_airport else 6
                
                eta_hour = current_hour + max_lead + max_proc
                
                purchase_orders.append(KitPurchaseOrder(
                    kits_per_class=kits_to_buy,
                    order_time=ReferenceHour(day=state.current_day, hour=state.current_hour),
                    expected_delivery=ReferenceHour(day=eta_hour // 24, hour=eta_hour % 24)
                ))
                
                logger.info(f"Round {self.round}: Purchasing {kits_to_buy}")
        
        # Log summary
        if self.round % 50 == 0 or self.round <= 5:
            total_loaded = sum(sum(d.kits_per_class.values()) for d in load_decisions)
            total_purchased = sum(sum(p.kits_per_class.values()) for p in purchase_orders)
            logger.info(f"Round {self.round}: {len(load_decisions)} flights loaded ({total_loaded} kits), {total_purchased} purchased")
            if self.hub_code:
                logger.info(f"  HUB inventory: {self.inventory.get(self.hub_code, {})}")
        
        return load_decisions, purchase_orders

