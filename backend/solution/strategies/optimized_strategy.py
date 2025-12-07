"""
OPTIMIZED Strategy - Minimizes total cost by balancing:
- Movement cost (loading kits)
- Unfulfilled penalty (not loading kits)
- Purchase cost (buying kits)

Key insight: Sometimes it's CHEAPER to not load kits!
- Movement cost: ~$1000/kit (for long distance flights)
- Unfulfilled penalty: ~$800/kit average

So for long flights, we might skip loading some classes.
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

# Cost parameters
KIT_WEIGHTS = {"FIRST": 15, "BUSINESS": 12, "PREMIUM_ECONOMY": 8, "ECONOMY": 5}
KIT_COSTS = {"FIRST": 500, "BUSINESS": 150, "PREMIUM_ECONOMY": 75, "ECONOMY": 50}
UNFULFILLED_FACTOR = {"FIRST": 2226, "BUSINESS": 1113, "PREMIUM_ECONOMY": 557, "ECONOMY": 278}


class OptimizedStrategy:
    """
    Optimized strategy that balances costs:
    - Only load if movement cost < unfulfilled penalty
    - Only purchase when critically needed
    - Prioritize high-value classes (FIRST, BUSINESS)
    """
    
    def __init__(self, config=None):
        self.config = config
        self.round = 0
        self.inventory: Dict[str, Dict[str, int]] = {}
        self.pending_arrivals: Dict[Tuple[str, int], Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.hub_code = None
        self.hub_capacity: Dict[str, int] = {}
        self.pending_purchases: Dict[str, int] = defaultdict(int)
        self.initialized = False
        
        # Tunable parameters
        self.purchase_threshold = 0.15  # Buy when stock < 15% capacity
        self.purchase_amount = 0.10     # Buy 10% of capacity at a time
        
        logger.info("OPTIMIZED STRATEGY initialized")
    
    def _initialize_from_airports(self, airports: Dict[str, Airport]):
        if self.initialized:
            return
        for code, airport in airports.items():
            self.inventory[code] = dict(airport.current_inventory)
            if airport.is_hub:
                self.hub_code = code
                self.hub_capacity = dict(airport.storage_capacity)
        self.initialized = True
    
    def _process_arrivals(self, current_hour: int):
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
        if airport_code not in self.inventory:
            return 0
        return max(0, self.inventory[airport_code].get(class_type, 0))
    
    def _consume(self, airport_code: str, class_type: str, quantity: int):
        if airport_code not in self.inventory:
            self.inventory[airport_code] = {}
        current = self.inventory[airport_code].get(class_type, 0)
        self.inventory[airport_code][class_type] = current - quantity
    
    def _schedule_arrival(self, airport_code: str, arrival_hour: int, processing_time: int, kits: Dict[str, int]):
        ready_hour = arrival_hour + processing_time
        for class_type, qty in kits.items():
            self.pending_arrivals[(airport_code, ready_hour)][class_type] += qty
    
    def _should_load(self, class_type: str, distance: float, fuel_cost: float, origin_airport: Airport) -> bool:
        """
        Decide if loading is cost-effective.
        Compare: movement_cost vs unfulfilled_penalty
        """
        weight = KIT_WEIGHTS.get(class_type, 10)
        movement_cost_per_kit = distance * fuel_cost * weight
        
        # Unfulfilled penalty per kit (distance-based)
        unfulfilled_cost_per_kit = UNFULFILLED_FACTOR.get(class_type, 500) * distance / 1000
        
        # Add loading cost
        loading_cost = origin_airport.loading_costs.get(class_type, 1) if origin_airport else 1
        
        total_load_cost = movement_cost_per_kit + loading_cost
        
        # Load only if it's cheaper than unfulfilled penalty
        return total_load_cost < unfulfilled_cost_per_kit
    
    def record_penalties(self, penalties: List[Dict]) -> None:
        pass
    
    def optimize(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        
        self.round += 1
        current_hour = state.current_day * 24 + state.current_hour
        
        self._initialize_from_airports(airports)
        self._process_arrivals(current_hour)
        
        load_decisions = []
        purchase_orders = []
        
        for flight in flights:
            flight_hour = flight.scheduled_departure.day * 24 + flight.scheduled_departure.hour
            if flight_hour != current_hour:
                continue
            
            origin = flight.origin
            destination = flight.destination
            aircraft = aircraft_types.get(flight.aircraft_type)
            origin_airport = airports.get(origin)
            dest_airport = airports.get(destination)
            
            if not aircraft:
                continue
            
            passengers = flight.actual_passengers or flight.planned_passengers
            fuel_cost = aircraft.fuel_cost_per_km
            distance = flight.planned_distance
            
            kits_to_load = {}
            
            for class_type in CLASS_TYPES:
                pax = passengers.get(class_type, 0)
                if pax == 0:
                    continue
                
                # Check if loading is cost-effective
                if not self._should_load(class_type, distance, fuel_cost, origin_airport):
                    # Skip loading - unfulfilled penalty is cheaper
                    continue
                
                available = self._get_available(origin, class_type)
                capacity = aircraft.kit_capacity.get(class_type, 0)
                
                load = min(pax, available, capacity)
                
                if load > 0:
                    kits_to_load[class_type] = load
                    self._consume(origin, class_type, load)
                    
                    if dest_airport:
                        proc_time = dest_airport.processing_times.get(class_type, 6)
                        arrival_hour = flight.scheduled_arrival.day * 24 + flight.scheduled_arrival.hour
                        self._schedule_arrival(destination, arrival_hour, proc_time, {class_type: load})
            
            if kits_to_load:
                load_decisions.append(KitLoadDecision(
                    flight_id=flight.flight_id,
                    kits_per_class=kits_to_load
                ))
        
        # Purchase only when critically needed
        if self.hub_code and self.round % 48 == 1:  # Every 2 days
            hub_inv = self.inventory.get(self.hub_code, {})
            hub_cap = self.hub_capacity
            
            kits_to_buy = {}
            
            for class_type in CLASS_TYPES:
                current_stock = hub_inv.get(class_type, 0)
                capacity = hub_cap.get(class_type, 0)
                pending = self.pending_purchases.get(class_type, 0)
                
                room = capacity - current_stock - pending
                threshold = int(capacity * self.purchase_threshold)
                
                if current_stock < threshold and room > 0:
                    buy_amount = min(int(capacity * self.purchase_amount), room)
                    if buy_amount > 0:
                        kits_to_buy[class_type] = buy_amount
                        self.pending_purchases[class_type] += buy_amount
            
            if kits_to_buy:
                max_lead = max(int(KIT_DEFINITIONS[c]["lead_time"]) for c in kits_to_buy)
                hub_airport = airports.get(self.hub_code)
                max_proc = max(hub_airport.processing_times.get(c, 6) for c in kits_to_buy) if hub_airport else 6
                eta_hour = current_hour + max_lead + max_proc
                
                purchase_orders.append(KitPurchaseOrder(
                    kits_per_class=kits_to_buy,
                    order_time=ReferenceHour(day=state.current_day, hour=state.current_hour),
                    expected_delivery=ReferenceHour(day=eta_hour // 24, hour=eta_hour % 24)
                ))
        
        return load_decisions, purchase_orders

