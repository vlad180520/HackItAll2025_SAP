"""Simple reactive strategy - loads passengers, buys when penalties occur.

This strategy does NOT try to track inventory locally because:
1. The API doesn't expose current inventory
2. Local tracking always drifts from reality
3. Simpler is more robust

Instead, it:
1. Loads exactly what passengers need on each flight
2. Reacts to NEGATIVE_INVENTORY penalties by purchasing
3. Trusts the system's initial stock + return flows
"""

import logging
from typing import Dict, List, Tuple
from collections import defaultdict

from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.airport import Airport
from models.aircraft import AircraftType
from solution.config import SolutionConfig
from config import CLASS_TYPES, KIT_DEFINITIONS

logger = logging.getLogger(__name__)

# API purchase limits
API_PURCHASE_LIMITS = {
    "FIRST": 42000,
    "BUSINESS": 42000,
    "PREMIUM_ECONOMY": 1000,
    "ECONOMY": 42000,
}


class SimpleReactiveStrategy:
    """Simple strategy: load passengers, buy reactively.
    
    Key principles:
    - Don't track inventory (we can't know the real state)
    - Load what passengers need
    - React to penalties by purchasing
    """
    
    def __init__(self, config: SolutionConfig):
        self.config = config
        self.horizon_hours = 4
        
        # Track penalties from previous rounds to inform purchases
        self.recent_negative_inventory: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.rounds_since_purchase = 0
        
        logger.info("SimpleReactiveStrategy initialized")
    
    def record_penalties(self, penalties: List[Dict]) -> None:
        """Record negative inventory penalties for reactive purchasing."""
        for penalty in penalties:
            code = penalty.get("code", "")
            if "NEGATIVE_INVENTORY" in code:
                reason = penalty.get("reason", "")
                # Parse: "Negative inventory for airport XXX kit type YYY of -ZZZ kits"
                parts = reason.split()
                if len(parts) >= 9:
                    try:
                        airport = parts[4]
                        kit_type = parts[7]  # e.g., "D_ECONOMY" -> need to map
                        qty = abs(int(parts[-2]))
                        
                        # Map kit type codes
                        type_map = {
                            "A_FIRST_CLASS": "FIRST",
                            "B_BUSINESS": "BUSINESS",
                            "C_PREMIUM_ECONOMY": "PREMIUM_ECONOMY",
                            "D_ECONOMY": "ECONOMY",
                        }
                        class_type = type_map.get(kit_type, kit_type)
                        
                        self.recent_negative_inventory[airport][class_type] += qty
                        logger.info(f"Recorded negative inventory: {airport} {class_type} -{qty}")
                    except (ValueError, IndexError):
                        pass
    
    def optimize(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """Main optimization: load passengers, buy reactively."""
        
        current_time = ReferenceHour(day=state.current_day, hour=state.current_hour)
        now_hours = current_time.to_hours()
        
        logger.info(f"SimpleStrategy optimizing at {current_time.day}d{current_time.hour}h")
        
        # Get flights departing within horizon
        loading_flights = self._get_loading_flights(flights, now_hours)
        
        # Load passengers + extra on outbound flights to replenish outstations
        load_decisions = self._compute_loads(loading_flights, aircraft_types, airports)
        
        # Reactive purchasing based on penalties
        purchase_orders = self._compute_purchases(state, airports, now_hours)
        
        self.rounds_since_purchase += 1
        
        total_purchases = sum(purchase_orders[0].kits_per_class.values()) if purchase_orders else 0
        logger.info(f"SimpleStrategy: {len(load_decisions)} loads, {total_purchases} purchases")
        
        return load_decisions, purchase_orders
    
    def _get_loading_flights(self, flights: List[Flight], now_hours: int) -> List[Flight]:
        """Get flights departing within horizon."""
        horizon_end = now_hours + self.horizon_hours
        return [
            f for f in flights
            if now_hours <= f.scheduled_departure.to_hours() < horizon_end
        ]
    
    def _compute_loads(
        self,
        flights: List[Flight],
        aircraft_types: Dict[str, AircraftType],
        airports: Dict[str, Airport],
    ) -> List[KitLoadDecision]:
        """Compute loads: passengers + extra for outstation replenishment.
        
        Key insight: Outbound flights (HUB→outstation) should carry EXTRA kits
        to replenish outstation inventory for return flights.
        """
        decisions = []
        
        # Find HUB
        hub_code = None
        for code, airport in airports.items():
            if airport.is_hub:
                hub_code = code
                break
        
        for flight in flights:
            aircraft = aircraft_types.get(flight.aircraft_type)
            if not aircraft:
                continue
            
            kits_per_class = {}
            is_outbound = (flight.origin == hub_code)  # HUB → outstation
            
            for class_type in CLASS_TYPES:
                passengers = flight.planned_passengers.get(class_type, 0)
                capacity = aircraft.kit_capacity.get(class_type, 0)
                
                if is_outbound:
                    # OUTBOUND: Load passengers + 30% extra to replenish outstation
                    # This ensures outstations have kits for return flights
                    target = int(passengers * 1.3)
                else:
                    # INBOUND (outstation → HUB): Just load what passengers need
                    target = passengers
                
                # Cap by aircraft capacity
                load = min(target, capacity)
                
                if load > 0:
                    kits_per_class[class_type] = load
            
            if kits_per_class:
                decisions.append(KitLoadDecision(
                    flight_id=flight.flight_id,
                    kits_per_class=kits_per_class
                ))
        
        return decisions
    
    def _compute_purchases(
        self,
        state: GameState,
        airports: Dict[str, Airport],
        now_hours: int,
    ) -> List[KitPurchaseOrder]:
        """Reactive purchasing based on negative inventory penalties."""
        
        # Find HUB
        hub_code = None
        hub_airport = None
        for code, airport in airports.items():
            if airport.is_hub:
                hub_code = code
                hub_airport = airport
                break
        
        if not hub_code:
            return []
        
        # Don't buy every round - let system stabilize
        if self.rounds_since_purchase < 3 and not self.recent_negative_inventory:
            return []
        
        # Calculate needed purchases based on penalties
        kits_per_class = {}
        
        # Aggregate all negative inventory (system-wide shortage)
        for airport_code, shortages in self.recent_negative_inventory.items():
            for class_type, shortage in shortages.items():
                if class_type not in kits_per_class:
                    kits_per_class[class_type] = 0
                # Buy 150% of shortage to build buffer
                kits_per_class[class_type] += int(shortage * 1.5)
        
        # Clear recorded penalties
        self.recent_negative_inventory.clear()
        
        if not kits_per_class:
            # Early game proactive purchase (first 24 hours)
            if now_hours < 24 and self.rounds_since_purchase >= 12:
                # Small proactive purchase to prevent early stockouts
                kits_per_class = {
                    "FIRST": 500,
                    "BUSINESS": 2000,
                    "PREMIUM_ECONOMY": 1000,
                    "ECONOMY": 10000,
                }
            else:
                return []
        
        # Clamp to API limits
        for class_type in kits_per_class:
            api_limit = API_PURCHASE_LIMITS.get(class_type, 42000)
            if kits_per_class[class_type] > api_limit:
                kits_per_class[class_type] = api_limit
        
        # Remove zero purchases
        kits_per_class = {k: v for k, v in kits_per_class.items() if v > 0}
        
        if not kits_per_class:
            return []
        
        # Calculate delivery time
        max_lead_time = max(
            int(KIT_DEFINITIONS[ct]["lead_time"])
            for ct in kits_per_class.keys()
        )
        max_processing = max(
            hub_airport.processing_times.get(ct, 0)
            for ct in kits_per_class.keys()
        )
        eta_hours = now_hours + max_lead_time + max_processing
        
        expected_delivery = ReferenceHour(
            day=eta_hours // 24,
            hour=eta_hours % 24
        )
        
        self.rounds_since_purchase = 0
        
        logger.info(f"PURCHASE ORDER: {kits_per_class}")
        
        return [KitPurchaseOrder(
            kits_per_class=kits_per_class,
            order_time=ReferenceHour(day=state.current_day, hour=state.current_hour),
            expected_delivery=expected_delivery
        )]

