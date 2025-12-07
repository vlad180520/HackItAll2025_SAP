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
            
            # NOTE: We do NOT track arrival movements locally!
            # The API handles kit arrivals at destinations internally.
            # We only track origin deductions (to know available stock for loading).
            
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
            # Find HUB airport code from inventory keys
            hub_code = "HUB1"  # Default
            for airport_code in self.state.airport_inventories.keys():
                if airport_code.upper().startswith("HUB"):
                    hub_code = airport_code
                    break
            
            # Create delivery movement
            delivery_movement = KitMovement(
                movement_type="DELIVERY",
                airport=hub_code,
                kits_per_class=order.kits_per_class,
                execute_time=order.expected_delivery,
            )
            self.state.pending_movements.append(delivery_movement)
            
            logger.info(
                f"Purchase order scheduled: {order.kits_per_class} "
                f"delivery to {hub_code} at day {order.expected_delivery.day} hour {order.expected_delivery.hour}"
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
                # NOTE: We do NOT track load arrivals locally!
                # The API handles inventory tracking for flight arrivals internally.
                # We only track what WE know about (our load decisions and purchases).
                # Adding arrivals here would double-count since API already does it.
                logger.debug(
                    f"Skipping load arrival tracking for {airport_code} "
                    f"(API handles this internally)"
                )
                
            elif movement.movement_type == "DELIVERY":
                # Purchased kits arrive at HUB
                for class_type, quantity in movement.kits_per_class.items():
                    current = self.state.airport_inventories[airport_code].get(class_type, 0)
                    self.state.airport_inventories[airport_code][class_type] = current + quantity
            
            # Remove from pending
            self.state.pending_movements.remove(movement)
        
        # NOTE: We do NOT track processing completion for LOAD movements
        # (arrivals are handled by API internally)
        # We only track DELIVERY (purchase) arrivals above
        
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

