"""State manager for game state transitions and kit movements."""

import logging
from typing import Dict, List, Tuple, Optional
from models.game_state import GameState, KitMovement
from models.flight import Flight, ReferenceHour
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.airport import Airport

logger = logging.getLogger(__name__)


class StateManager:
    """Manages game state transitions and time-based kit movements."""
    
    def __init__(self, initial_state: GameState):
        """
        Initialize state manager with initial game state.
        
        Args:
            initial_state: Initial game state
        """
        self.state = initial_state
        logger.info(f"StateManager initialized at day {initial_state.current_day}, hour {initial_state.current_hour}")
    
    def apply_kit_loads(self, decisions: List[KitLoadDecision], flights: List[Flight]) -> None:
        """
        Apply kit load decisions: decrement departure airport inventory and create pending movements.
        
        Args:
            decisions: List of kit load decisions
            flights: List of flights (to get departure/arrival info)
        """
        flight_dict = {f.flight_id: f for f in flights}
        
        for decision in decisions:
            if decision.flight_id not in flight_dict:
                logger.warning(f"Flight {decision.flight_id} not found, skipping load decision")
                continue
            
            flight = flight_dict[decision.flight_id]
            origin = flight.origin
            
            # Decrement inventory at origin
            if origin not in self.state.airport_inventories:
                self.state.airport_inventories[origin] = {}
            
            for class_type, quantity in decision.kits_per_class.items():
                current = self.state.airport_inventories[origin].get(class_type, 0)
                new_quantity = current - quantity
                self.state.airport_inventories[origin][class_type] = new_quantity
                
                if new_quantity < 0:
                    logger.warning(
                        f"Negative inventory at {origin} for {class_type}: {new_quantity}"
                    )
            
            # Create pending movement for arrival
            arrival_movement = KitMovement(
                movement_type="LOAD",
                airport=flight.destination,
                kits_per_class=decision.kits_per_class,
                execute_time=flight.scheduled_arrival,
            )
            self.state.pending_movements.append(arrival_movement)
            
            logger.debug(
                f"Applied load decision for flight {decision.flight_id}: "
                f"{decision.kits_per_class} from {origin} to {flight.destination}"
            )
    
    def apply_purchases(self, orders: List[KitPurchaseOrder]) -> None:
        """
        Apply purchase orders: create pending delivery movements to HUB.
        
        Args:
            orders: List of purchase orders
        """
        for order in orders:
            # Purchases are delivered to HUB
            hub_code = None
            for airport_code, inventory in self.state.airport_inventories.items():
                # Find HUB (assuming we track this separately or check airport.is_hub)
                # For now, we'll need to pass hub_code or find it from airport data
                # This is a simplification - in practice, we'd have airport objects
                pass
            
            # Create delivery movement
            delivery_movement = KitMovement(
                movement_type="DELIVERY",
                airport=hub_code or "HUB",  # Default to "HUB" if not found
                kits_per_class=order.kits_per_class,
                execute_time=order.expected_delivery,
            )
            self.state.pending_movements.append(delivery_movement)
            
            logger.debug(
                f"Applied purchase order: {order.kits_per_class} "
                f"delivery at {order.expected_delivery}"
            )
    
    def advance_time_to(self, day: int, hour: int, airports: Dict[str, Airport]) -> None:
        """
        Process all movements with execute_time <= (day, hour).
        
        Args:
            day: Target day
            hour: Target hour
            airports: Dictionary of airport objects for processing times
        """
        target_time = ReferenceHour(day=day, hour=hour)
        
        # Process pending movements that are due
        movements_to_process = [
            m for m in self.state.pending_movements
            if m.execute_time <= target_time
        ]
        
        for movement in movements_to_process:
            airport_code = movement.airport
            
            if airport_code not in self.state.airport_inventories:
                self.state.airport_inventories[airport_code] = {}
            
            if movement.movement_type == "LOAD":
                # Kits arrive at destination, enter processing queue
                if airport_code not in self.state.in_process_kits:
                    self.state.in_process_kits[airport_code] = []
                
                # Get processing time from airport
                airport = airports.get(airport_code)
                if airport:
                    processing_time = max(
                        airport.processing_times.get(class_type, 2)
                        for class_type in movement.kits_per_class.keys()
                    )
                    processing_complete = ReferenceHour(
                        day=movement.execute_time.day,
                        hour=movement.execute_time.hour + processing_time,
                    )
                    
                    processing_movement = KitMovement(
                        movement_type="PROCESSING",
                        airport=airport_code,
                        kits_per_class=movement.kits_per_class,
                        execute_time=processing_complete,
                    )
                    self.state.in_process_kits[airport_code].append(processing_movement)
                else:
                    # No airport data, assume immediate availability
                    for class_type, quantity in movement.kits_per_class.items():
                        current = self.state.airport_inventories[airport_code].get(class_type, 0)
                        self.state.airport_inventories[airport_code][class_type] = current + quantity
                
            elif movement.movement_type == "DELIVERY":
                # Purchased kits arrive at HUB
                for class_type, quantity in movement.kits_per_class.items():
                    current = self.state.airport_inventories[airport_code].get(class_type, 0)
                    self.state.airport_inventories[airport_code][class_type] = current + quantity
            
            # Remove from pending
            self.state.pending_movements.remove(movement)
        
        # Process completed processing movements
        for airport_code, processing_list in list(self.state.in_process_kits.items()):
            completed = [
                m for m in processing_list
                if m.execute_time <= target_time
            ]
            
            for movement in completed:
                # Kits become available in inventory
                for class_type, quantity in movement.kits_per_class.items():
                    current = self.state.airport_inventories[airport_code].get(class_type, 0)
                    self.state.airport_inventories[airport_code][class_type] = current + quantity
                
                processing_list.remove(movement)
            
            # Clean up empty lists
            if not processing_list:
                del self.state.in_process_kits[airport_code]
        
        # Update current time
        self.state.current_day = day
        self.state.current_hour = hour
    
    def get_inventory(self, airport_code: str, kit_class: str) -> int:
        """
        Get current inventory for an airport and kit class.
        
        Args:
            airport_code: Airport code
            kit_class: Kit class (FIRST, BUSINESS, etc.)
            
        Returns:
            Current inventory quantity
        """
        return self.state.airport_inventories.get(airport_code, {}).get(kit_class, 0)
    
    def get_available_inventory(
        self, airport_code: str, kit_class: str, flights: List[Flight]
    ) -> int:
        """
        Get available inventory (current minus reserved for pending departures).
        
        Args:
            airport_code: Airport code
            kit_class: Kit class
            flights: List of flights to check for pending departures
            
        Returns:
            Available inventory quantity
        """
        current = self.get_inventory(airport_code, kit_class)
        
        # Calculate reserved inventory (kits already loaded on departing flights)
        # This is a simplification - in practice, we'd track this more carefully
        reserved = 0
        current_time = self.state.get_current_time()
        
        for movement in self.state.pending_movements:
            if movement.airport == airport_code and movement.movement_type == "LOAD":
                # Check if this is a departure (not arrival)
                # This is simplified - we'd need to track which movements are departures
                pass
        
        return max(0, current - reserved)
    
    def check_negative_inventories(self) -> List[Tuple[str, str, int]]:
        """
        Check for negative inventories across all airports.
        
        Returns:
            List of (airport_code, class_type, negative_amount) tuples
        """
        negatives = []
        
        for airport_code, inventory in self.state.airport_inventories.items():
            for class_type, quantity in inventory.items():
                if quantity < 0:
                    negatives.append((airport_code, class_type, quantity))
        
        return negatives
    
    @property
    def current_state(self) -> GameState:
        """Get current game state (read-only)."""
        return self.state

