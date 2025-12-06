"""Greedy optimizer for kit management decisions."""

import logging
from typing import Dict, List, Tuple
from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.airport import Airport
from models.aircraft import AircraftType
from config import Config

logger = logging.getLogger(__name__)


class GreedyOptimizer:
    """Simple greedy rule-based optimizer."""
    
    def __init__(self, config: Config):
        """
        Initialize greedy optimizer.
        
        Args:
            config: Configuration object with optimizer parameters
        """
        self.config = config
        self.safety_buffer = config.SAFETY_BUFFER
        self.reorder_threshold = config.REORDER_THRESHOLD
        self.target_stock_level = config.TARGET_STOCK_LEVEL
        self.lookahead_hours = config.LOOKAHEAD_HOURS
    
    def decide(
        self,
        state: GameState,
        visible_flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft: Dict[str, AircraftType],
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder], str]:
        """
        Produce decisions using greedy rule-based logic.
        
        Strategy:
        - For each departing flight: load min(aircraft_kit_capacity[class], max(planned_passengers[class], 0))
        - If inventory insufficient, load what's available (allow zero)
        - For HUB purchases: if projected inventory for next 24 hours < reorder_threshold,
          order up to target_stock_level
        
        Args:
            state: Current game state
            visible_flights: List of flights visible at current time
            airports: Dictionary of airports
            aircraft: Dictionary of aircraft types
            
        Returns:
            Tuple of (decisions, purchases, rationale)
        """
        decisions = []
        purchases = []
        rationale_parts = []
        
        current_time = state.get_current_time()
        
        # Process departing flights
        for flight in visible_flights:
            # Only process flights departing at or after current time
            if flight.scheduled_departure < current_time:
                continue
            
            # Only process flights that haven't departed yet
            if flight.actual_departure is not None:
                continue
            
            aircraft_type = aircraft.get(flight.aircraft_type)
            if not aircraft_type:
                logger.warning(f"Unknown aircraft type {flight.aircraft_type} for flight {flight.flight_id}")
                continue
            
            origin_airport = airports.get(flight.origin)
            if not origin_airport:
                logger.warning(f"Unknown airport {flight.origin} for flight {flight.flight_id}")
                continue
            
            # Get passenger counts
            passengers = flight.actual_passengers or flight.planned_passengers
            
            # Determine kits to load per class
            kits_per_class = {}
            decision_rationale = []
            
            for class_type in ["FIRST", "BUSINESS", "PREMIUM_ECONOMY", "ECONOMY"]:
                passenger_count = passengers.get(class_type, 0)
                aircraft_capacity = aircraft_type.kit_capacity.get(class_type, 0)
                available_inventory = state.airport_inventories.get(flight.origin, {}).get(class_type, 0)
                
                # Target: min(capacity, passenger_count + safety_buffer)
                target_kits = min(aircraft_capacity, max(0, passenger_count + self.safety_buffer))
                
                # Load what's available (up to target)
                kits_to_load = min(target_kits, available_inventory)
                
                if kits_to_load < target_kits and target_kits > 0:
                    decision_rationale.append(
                        f"{class_type}: wanted {target_kits}, loaded {kits_to_load} "
                        f"(inventory: {available_inventory})"
                    )
                else:
                    decision_rationale.append(
                        f"{class_type}: loaded {kits_to_load} (passengers: {passenger_count}, "
                        f"capacity: {aircraft_capacity})"
                    )
                
                kits_per_class[class_type] = kits_to_load
            
            decision = KitLoadDecision(
                flight_id=flight.flight_id,
                kits_per_class=kits_per_class,
            )
            decisions.append(decision)
            
            rationale_parts.append(
                f"Flight {flight.flight_id} ({flight.origin}->{flight.destination}): "
                f"{'; '.join(decision_rationale)}"
            )
        
        # Determine HUB purchases
        hub_airports = [code for code, airport in airports.items() if airport.is_hub]
        
        if hub_airports:
            hub_code = hub_airports[0]  # Use first HUB
            hub_inventory = state.airport_inventories.get(hub_code, {})
            
            # Project inventory for next lookahead_hours
            # Simplified: check flights departing from HUB in next 24 hours
            lookahead_end = ReferenceHour(
                day=current_time.day,
                hour=current_time.hour + self.lookahead_hours,
            )
            
            projected_demand = {}
            for flight in visible_flights:
                if (
                    flight.origin == hub_code
                    and flight.scheduled_departure >= current_time
                    and flight.scheduled_departure <= lookahead_end
                ):
                    passengers = flight.actual_passengers or flight.planned_passengers
                    for class_type, count in passengers.items():
                        projected_demand[class_type] = projected_demand.get(class_type, 0) + count
            
            # Determine purchase orders
            purchase_kits = {}
            purchase_rationale = []
            
            for class_type in ["FIRST", "BUSINESS", "PREMIUM_ECONOMY", "ECONOMY"]:
                current_stock = hub_inventory.get(class_type, 0)
                projected_usage = projected_demand.get(class_type, 0)
                projected_stock = current_stock - projected_usage
                
                if projected_stock < self.reorder_threshold:
                    # Need to order
                    order_quantity = self.target_stock_level - projected_stock
                    order_quantity = max(0, order_quantity)  # Don't order negative
                    
                    if order_quantity > 0:
                        purchase_kits[class_type] = order_quantity
                        purchase_rationale.append(
                            f"{class_type}: current={current_stock}, "
                            f"projected={projected_stock}, ordering={order_quantity}"
                        )
            
            if purchase_kits:
                # Calculate delivery time (lead time from config)
                lead_time = 24  # Default lead time
                delivery_time = ReferenceHour(
                    day=current_time.day + (current_time.hour + lead_time) // 24,
                    hour=(current_time.hour + lead_time) % 24,
                )
                
                purchase = KitPurchaseOrder(
                    kits_per_class=purchase_kits,
                    order_time=current_time,
                    expected_delivery=delivery_time,
                )
                purchases.append(purchase)
                
                rationale_parts.append(
                    f"HUB purchase: {', '.join(purchase_rationale)}"
                )
            else:
                rationale_parts.append("HUB purchase: No orders needed (sufficient stock)")
        else:
            rationale_parts.append("HUB purchase: No HUB airport found")
        
        rationale = " | ".join(rationale_parts)
        logger.debug(f"Optimizer decisions: {len(decisions)} loads, {len(purchases)} purchases")
        
        return decisions, purchases, rationale

