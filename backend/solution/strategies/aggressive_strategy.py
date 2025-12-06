"""Aggressive over-purchasing strategy to minimize penalties.

This strategy prioritizes ZERO SLACK at all costs by:
1. Always loading EXACT passenger count + LARGE buffer
2. Aggressively purchasing to maintain 200%+ inventory
3. Pre-positioning for return flights
4. Never, ever leaving passengers without kits
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

logger = logging.getLogger(__name__)


class AggressiveStrategy:
    """Ultra-aggressive strategy: ZERO slack, massive over-purchasing."""
    
    CLASS_KEYS = ["FIRST", "BUSINESS", "PREMIUM_ECONOMY", "ECONOMY"]
    
    LEAD_TIMES = {
        "FIRST": 48,
        "BUSINESS": 36,
        "PREMIUM_ECONOMY": 24,
        "ECONOMY": 12,
    }
    
    KIT_COSTS = {
        "FIRST": 50.0,
        "BUSINESS": 30.0,
        "PREMIUM_ECONOMY": 15.0,
        "ECONOMY": 10.0,
    }
    
    def __init__(self, config: SolutionConfig):
        """Initialize aggressive strategy."""
        self.config = config
        logger.info("AggressiveStrategy initialized: ZERO SLACK AT ALL COSTS")
    
    def optimize(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """
        Optimize with aggressive over-purchasing.
        
        Strategy:
        1. Load EVERY flight with pax + LARGE buffer
        2. Purchase MASSIVELY to maintain 200% future demand
        3. NEVER risk negative inventory
        """
        current_time = ReferenceHour(day=state.current_day, hour=state.current_hour)
        now_hours = current_time.to_hours()
        
        loads = []
        
        # STEP 1: Load ALL departing flights with GENEROUS buffers
        for flight in flights:
            if flight.scheduled_departure.to_hours() != now_hours:
                continue
            
            if flight.origin not in state.airport_inventories:
                logger.warning(f"No inventory data for {flight.origin}")
                continue
            
            aircraft = aircraft_types.get(flight.aircraft_type)
            if not aircraft:
                logger.warning(f"Unknown aircraft: {flight.aircraft_type}")
                continue
            
            passengers = self._get_passengers(flight)
            inventory = state.airport_inventories[flight.origin]
            distance = flight.planned_distance if hasattr(flight, 'planned_distance') else 1000
            
            kits_to_load = {}
            
            for cls in self.CLASS_KEYS:
                pax = passengers.get(cls, 0)
                if pax <= 0:
                    continue
                
                # AGGRESSIVE BUFFER calculation
                if distance >= 5000:
                    buffer = max(5, int(pax * 0.15))  # 15% or 5 kits minimum
                elif distance >= 1000:
                    buffer = max(3, int(pax * 0.10))  # 10% or 3 kits
                elif distance >= 333:
                    buffer = max(2, int(pax * 0.05))  # 5% or 2 kits
                else:
                    buffer = 1
                
                # Target load = passengers + buffer
                target = pax + buffer
                
                # Add pre-positioning for return flights
                if flight.origin == "HUB1" and flight.destination != "HUB1":
                    # Check destination inventory
                    dest_inv = state.airport_inventories.get(flight.destination, {}).get(cls, 0)
                    if dest_inv < pax * 2:  # If dest has less than 2x return demand
                        preposition = min(10, pax)  # Pre-position up to 1x pax count
                        target += preposition
                
                # Cap by aircraft capacity
                capacity = aircraft.kit_capacity.get(cls, 0)
                available = inventory.get(cls, 0)
                
                # Load as much as possible
                to_load = min(target, capacity, available)
                
                if to_load > 0:
                    kits_to_load[cls] = to_load
            
            if kits_to_load:
                loads.append(KitLoadDecision(
                    flight_id=flight.flight_id,
                    kits_per_class=kits_to_load
                ))
        
        # STEP 2: AGGRESSIVE PURCHASING - maintain 200% of 72h demand
        purchases = self._aggressive_purchasing(
            state, flights, now_hours
        )
        
        logger.info(f"Aggressive strategy: {len(loads)} loads, {len(purchases)} purchases")
        return loads, purchases
    
    def _aggressive_purchasing(
        self,
        state: GameState,
        flights: List[Flight],
        now_hours: int,
    ) -> List[KitPurchaseOrder]:
        """
        Purchase aggressively to maintain 200% of future demand.
        
        Philosophy: Better to waste money on over-purchasing than pay penalties!
        """
        # Calculate demand for next 72 hours (3 days)
        horizon_end = now_hours + 72
        future_demand = defaultdict(int)
        
        for flight in flights:
            dep_time = flight.scheduled_departure.to_hours()
            if now_hours <= dep_time <= horizon_end and flight.origin == "HUB1":
                passengers = self._get_passengers(flight)
                for cls, pax in passengers.items():
                    # Demand = pax + buffer (aggressive)
                    buffer = max(2, int(pax * 0.1))
                    future_demand[cls] += pax + buffer
        
        # Current HUB inventory
        hub_inv = state.airport_inventories.get("HUB1", {})
        
        # Purchase to maintain 200% of demand
        kits_to_purchase = {}
        
        for cls in self.CLASS_KEYS:
            current = hub_inv.get(cls, 0)
            demand_72h = future_demand[cls]
            
            # Target = 200% of 72h demand (very safe!)
            target = int(demand_72h * 2.0)
            
            # If current < target, purchase the difference
            if current < target:
                needed = target - current
                
                # Add extra safety margin
                needed = int(needed * 1.2)  # +20% extra safety
                
                # Minimum purchase to justify transaction
                if needed >= 5:
                    kits_to_purchase[cls] = needed
        
        if not kits_to_purchase:
            return []
        
        # Create purchase order
        current_time = ReferenceHour(
            day=now_hours // 24,
            hour=now_hours % 24
        )
        
        # Use longest lead time
        max_lead_time = max(
            self.LEAD_TIMES.get(cls, 24)
            for cls in kits_to_purchase.keys()
        )
        
        delivery_hours = now_hours + max_lead_time
        delivery_time = ReferenceHour(
            day=delivery_hours // 24,
            hour=delivery_hours % 24
        )
        
        logger.info(f"Purchasing: {sum(kits_to_purchase.values())} total kits")
        
        return [KitPurchaseOrder(
            kits_per_class=kits_to_purchase,
            order_time=current_time,
            expected_delivery=delivery_time
        )]
    
    def _get_passengers(self, flight: Flight) -> Dict[str, int]:
        """Get passenger forecast."""
        if flight.actual_passengers:
            return flight.actual_passengers.copy()
        return flight.planned_passengers.copy()
