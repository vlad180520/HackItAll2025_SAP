"""Validator module for pre-submission validation."""

import logging
from typing import Dict, List
from pydantic import BaseModel
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.game_state import GameState
from models.flight import Flight
from models.airport import Airport
from models.aircraft import AircraftType

logger = logging.getLogger(__name__)


class ValidationReport(BaseModel):
    """Validation report with errors, warnings, and estimated penalty."""
    
    errors: List[str]
    warnings: List[str]
    estimated_penalty: float
    
    def is_valid(self) -> bool:
        """Check if validation passed (no errors)."""
        return len(self.errors) == 0


class Validator:
    """Validates decisions before submission."""
    
    def __init__(
        self,
        airports: Dict[str, Airport],
        aircraft: Dict[str, AircraftType],
        kit_defs: Dict,
    ):
        """
        Initialize validator.
        
        Args:
            airports: Dictionary of airports
            aircraft: Dictionary of aircraft types
            kit_defs: Kit definitions dictionary
        """
        self.airports = airports
        self.aircraft = aircraft
        self.kit_defs = kit_defs
    
    def validate_decisions(
        self,
        decisions: List[KitLoadDecision],
        purchases: List[KitPurchaseOrder],
        state: GameState,
        flights: List[Flight],
    ) -> ValidationReport:
        """
        Validate decisions and purchases.
        
        Args:
            decisions: List of kit load decisions
            purchases: List of purchase orders
            state: Current game state
            flights: List of flights
            
        Returns:
            ValidationReport with errors and warnings
        """
        errors = []
        warnings = []
        estimated_penalty = 0.0
        
        flight_dict = {f.flight_id: f for f in flights}
        
        # Validate kit load decisions
        for decision in decisions:
            # Check flight exists
            if decision.flight_id not in flight_dict:
                errors.append(f"Flight {decision.flight_id} does not exist")
                continue
            
            flight = flight_dict[decision.flight_id]
            aircraft_type = self.aircraft.get(flight.aircraft_type)
            
            if not aircraft_type:
                warnings.append(
                    f"Unknown aircraft type {flight.aircraft_type} for flight {decision.flight_id}"
                )
                continue
            
            # Check aircraft capacity
            for class_type, quantity in decision.kits_per_class.items():
                capacity = aircraft_type.kit_capacity.get(class_type, 0)
                if quantity > capacity:
                    errors.append(
                        f"Flight {decision.flight_id}: {class_type} capacity exceeded "
                        f"({quantity} > {capacity})"
                    )
                    estimated_penalty += (quantity - capacity) * 2000.0  # FLIGHT_OVERLOAD_FACTOR
            
            # Check departure inventory
            origin_airport = self.airports.get(flight.origin)
            if origin_airport:
                for class_type, quantity in decision.kits_per_class.items():
                    available = state.airport_inventories.get(flight.origin, {}).get(class_type, 0)
                    if quantity > available:
                        warnings.append(
                            f"Flight {decision.flight_id}: Insufficient inventory at {flight.origin} "
                            f"for {class_type} ({quantity} > {available})"
                        )
                        estimated_penalty += (quantity - available) * 1000.0  # NEGATIVE_INVENTORY_FACTOR
            
            # Check passenger fulfillment
            passengers = flight.actual_passengers or flight.planned_passengers
            for class_type, passenger_count in passengers.items():
                kit_count = decision.kits_per_class.get(class_type, 0)
                if kit_count < passenger_count:
                    warnings.append(
                        f"Flight {decision.flight_id}: Unfulfilled passengers for {class_type} "
                        f"({kit_count} < {passenger_count})"
                    )
                    estimated_penalty += (passenger_count - kit_count) * 300.0  # UNFULFILLED_PASSENGERS_FACTOR
        
        # Validate purchases (must be at HUB)
        hub_airports = [
            code for code, airport in self.airports.items() if airport.is_hub
        ]
        
        for purchase in purchases:
            # Purchases are always at HUB, but we need to check timing
            current_time = state.get_current_time()
            if purchase.order_time < current_time:
                errors.append(
                    f"Purchase order time {purchase.order_time} is in the past"
                )
        
        # Check timing validity
        for decision in decisions:
            if decision.flight_id not in flight_dict:
                continue
            
            flight = flight_dict[decision.flight_id]
            current_time = state.get_current_time()
            
            # Flight should be departing at or after current time
            if flight.scheduled_departure < current_time:
                warnings.append(
                    f"Flight {decision.flight_id} departure {flight.scheduled_departure} "
                    f"is before current time {current_time}"
                )
        
        return ValidationReport(
            errors=errors,
            warnings=warnings,
            estimated_penalty=estimated_penalty,
        )

