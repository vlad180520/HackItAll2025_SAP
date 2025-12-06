"""
PENALTY-AWARE OPTIMAL STRATEGY

Algorithm: Distance-Aware Dynamic Buffer with Penalty Minimization

Based on mathematical analysis of penalty system (see PENALTY_ANALYSIS.py):
- OVERLOAD penalty: 500-10,000× operational cost → NEVER overload!
- UNFULFILLED penalty: 0.3×-6× operational cost (depends on distance)
- NEGATIVE_INVENTORY: 5342 penalty → NEVER go negative!
- Break-even distance: 333km (penalty = cost)

Key Insights:
1. For flights ≥ 333km (80% of flights): Unfulfilled penalty > kit cost
   → Use 1 kit buffer (saves money!)
2. For flights < 333km: Unfulfilled penalty < kit cost
   → No buffer at HUB (can restock), 1 buffer at outstations (safety)
3. Overload penalty is MASSIVE (500-10,000×) → Never exceed capacity!
4. Negative inventory is HUGE (5342) → Always maintain positive stock!

Expected: $400K-600K total cost (60-70% reduction vs baseline)
"""

import logging
from typing import Dict, List, Tuple
from collections import defaultdict

from models.game_state import GameState
from models.flight import Flight
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.airport import Airport
from models.aircraft import AircraftType
from solution.config import SolutionConfig

logger = logging.getLogger(__name__)


class PenaltyAwareStrategy:
    """
    Penalty-aware optimal strategy.
    Uses mathematical analysis to minimize total cost (operational + penalties).
    """
    
    def __init__(self, config: SolutionConfig):
        self.config = config
        self.demand_predictor = SmartDemandPredictor()
        self.purchase_optimizer = PenaltyAwarePurchasing(config)
        self.loading_optimizer = DistanceAwareLoading(config)
        self.transit_tracker = TransitKitTracker()
        
        logger.info("PENALTY-AWARE STRATEGY: Distance-based buffer optimization")
    
    def optimize(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """
        Optimize decisions with penalty awareness.
        """
        # Predict demand with lead times
        demand_forecast = self.demand_predictor.predict_demand(
            flights, state, airports
        )
        
        # Update transit tracking
        self.transit_tracker.update(state, flights)
        
        # Optimize purchases (54h ahead for First, 13h ahead for Economy)
        purchases = self.purchase_optimizer.optimize_purchases(
            state, demand_forecast, self.transit_tracker
        )
        
        # Optimize loading (distance-aware buffers)
        loads = self.loading_optimizer.optimize_loading(
            state, flights, airports, aircraft_types
        )
        
        return loads, purchases


class SmartDemandPredictor:
    """Predicts demand accounting for lead times and processing."""
    
    def predict_demand(
        self,
        flights: List[Flight],
        state: GameState,
        airports: Dict[str, Airport]
    ) -> Dict:
        """
        Predict demand for next 72h (max lead time 48h + processing 6h + buffer 18h).
        Returns: {class_type: {hour: quantity}}
        """
        demand_by_class = {
            'first': defaultdict(int),
            'business': defaultdict(int),
            'premium_economy': defaultdict(int),
            'economy': defaultdict(int)
        }
        
        current_time = state.current_time.to_hours()
        
        for flight in flights:
            departure_time = flight.scheduled_departure.to_hours()
            time_until_departure = departure_time - current_time
            
            # 72h forecast window
            if time_until_departure < 0 or time_until_departure > 72:
                continue
            
            # Use actual passengers if available (CHECKED_IN event)
            passengers_dict = (flight.actual_passengers 
                             if hasattr(flight, 'actual_passengers') and flight.actual_passengers 
                             else flight.planned_passengers)
            
            for class_type, passengers in passengers_dict.items():
                if passengers > 0:
                    # Add buffer based on distance
                    if flight.distance >= 333:  # Long flight
                        buffer = 1  # Unfulfilled penalty > cost
                    elif flight.origin != "HUB1":  # Outstation short flight
                        buffer = 1  # Safety (can't restock)
                    else:  # HUB short flight
                        buffer = 0  # No buffer (can restock)
                    
                    demand_by_class[class_type][departure_time] += passengers + buffer
        
        return demand_by_class


class TransitKitTracker:
    """Tracks kits in transit and processing."""
    
    def __init__(self):
        self.in_transit = defaultdict(int)
        self.in_processing = defaultdict(lambda: defaultdict(int))  # class -> hour -> qty
    
    def update(self, state: GameState, flights: List[Flight]):
        """Update tracking from game state."""
        self.in_transit = defaultdict(int)
        self.in_processing = defaultdict(lambda: defaultdict(int))
        
        # Track kits on return flights to HUB
        current_time = state.current_time.to_hours()
        
        for flight in flights:
            if flight.destination != "HUB1":
                continue
            
            arrival_time = flight.scheduled_arrival.to_hours()
            
            if arrival_time <= current_time or arrival_time > current_time + 72:
                continue
            
            # Kits will return on this flight
            # Estimate based on outbound capacity
            # (This is conservative - actual might be lower)
            pass  # TODO: Implement if flight load history available
    
    def get_available_at(self, class_type: str, hour: int) -> int:
        """Get kits that will be available by given hour."""
        total = 0
        
        # In transit kits
        total += self.in_transit.get(class_type, 0)
        
        # Processing kits that will be ready
        if class_type in self.in_processing:
            for ready_hour, qty in self.in_processing[class_type].items():
                if ready_hour <= hour:
                    total += qty
        
        return total


class PenaltyAwarePurchasing:
    """Purchase optimization considering lead times and penalties."""
    
    # Lead times from KitType.java
    LEAD_TIMES = {
        'first': 48,
        'business': 36,
        'premium_economy': 24,
        'economy': 12
    }
    
    # Processing times from config.py
    PROCESSING_TIMES = {
        'first': 6,
        'business': 4,
        'premium_economy': 2,
        'economy': 1
    }
    
    def __init__(self, config: SolutionConfig):
        self.config = config
    
    def optimize_purchases(
        self,
        state: GameState,
        demand_forecast: Dict,
        transit_tracker: TransitKitTracker
    ) -> List[KitPurchaseOrder]:
        """
        Purchase kits with lead time awareness.
        Buy when: current + transit + pending_orders < forecast + safety
        """
        purchases = []
        HUB_CODE = "HUB1"
        current_time = state.current_time.to_hours()
        
        hub_inventory = state.inventory.get(HUB_CODE, {})
        
        for class_type in ["first", "business", "premium_economy", "economy"]:
            current_stock = hub_inventory.get(class_type, 0)
            
            # Total lead time = delivery + processing
            lead_time = self.LEAD_TIMES[class_type]
            processing_time = self.PROCESSING_TIMES[class_type]
            total_time = lead_time + processing_time
            
            # Forecast demand from (now + total_time) to (now + 72h)
            forecast_start = current_time + total_time
            forecast_end = current_time + 72
            
            total_demand = 0
            for hour, qty in demand_forecast[class_type].items():
                if forecast_start <= hour <= forecast_end:
                    total_demand += qty
            
            # Available kits = stock + transit + processing
            in_transit = transit_tracker.get_available_at(class_type, forecast_start)
            total_available = current_stock + in_transit
            
            # Need to purchase?
            shortage = total_demand - total_available
            
            if shortage > 0:
                # Add safety margin (5-10 kits)
                safety_margin = 10 if class_type in ['first', 'business'] else 5
                quantity = shortage + safety_margin
                
                if quantity >= 3:  # Min order size
                    purchases.append(KitPurchaseOrder(
                        airport=HUB_CODE,
                        class_type=class_type,
                        quantity=quantity,
                        execution_time=state.current_time
                    ))
                    
                    logger.info(
                        f"PURCHASE {class_type}: {quantity} kits "
                        f"(stock={current_stock}, demand_72h={total_demand}, "
                        f"lead_time={total_time}h)"
                    )
        
        return purchases


class DistanceAwareLoading:
    """Loading optimization with distance-aware buffers."""
    
    BREAKEVEN_DISTANCE = 333  # km (when unfulfilled penalty = kit cost)
    
    def __init__(self, config: SolutionConfig):
        self.config = config
    
    def optimize_loading(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ) -> List[KitLoadDecision]:
        """
        Load kits with distance-aware buffer.
        - Long flights (≥333km): +1 buffer (penalty > cost)
        - Short HUB flights (<333km): +0 buffer (can restock)
        - Short outstation flights (<333km): +1 buffer (safety)
        """
        load_decisions = []
        HUB_CODE = "HUB1"
        current_time = state.current_time.to_hours()
        
        for flight in flights:
            departure_time = flight.scheduled_departure.to_hours()
            
            # Only load flights departing NOW
            if departure_time != current_time:
                continue
            
            if flight.origin not in state.inventory:
                continue
            
            inventory = state.inventory[flight.origin].copy()
            aircraft_type = aircraft_types.get(flight.aircraft_type)
            
            if not aircraft_type:
                continue
            
            is_hub = (flight.origin == HUB_CODE)
            is_long_flight = (flight.distance >= self.BREAKEVEN_DISTANCE)
            
            kits_to_load = {}
            
            # Use ACTUAL passengers when available
            passengers_dict = (flight.actual_passengers 
                             if hasattr(flight, 'actual_passengers') and flight.actual_passengers 
                             else flight.planned_passengers)
            
            for class_type, passengers in passengers_dict.items():
                if passengers <= 0:
                    continue
                
                # Calculate buffer based on distance and location
                if is_long_flight:
                    # Long flight: Unfulfilled penalty > cost
                    buffer = 1
                elif is_hub:
                    # Short HUB flight: Can restock, no buffer
                    buffer = 0
                else:
                    # Short outstation flight: Safety buffer
                    buffer = 1
                
                needed = passengers + buffer
                aircraft_capacity = aircraft_type.kit_capacity.get(class_type, 0)
                
                if aircraft_capacity <= 0:
                    continue
                
                # NEVER overload! (500-10,000× penalty!)
                needed = min(needed, aircraft_capacity)
                available = inventory.get(class_type, 0)
                
                # Load what we can (avoid negative inventory penalty 5342!)
                if available < passengers:
                    logger.warning(
                        f"SHORTAGE {flight.flight_number} {flight.origin}/{class_type}: "
                        f"need {passengers}, have {available}, loading {min(available, aircraft_capacity)}"
                    )
                    kits_to_load[class_type] = min(available, aircraft_capacity)
                else:
                    kits_to_load[class_type] = min(needed, available, aircraft_capacity)
                
                inventory[class_type] = inventory.get(class_type, 0) - kits_to_load.get(class_type, 0)
            
            if kits_to_load:
                load_decisions.append(KitLoadDecision(
                    flight_id=flight.flight_id,
                    kits_per_class=kits_to_load
                ))
                
                # Log buffer usage
                buffer_info = "long" if is_long_flight else ("hub-short" if is_hub else "out-short")
                logger.debug(f"LOAD {flight.flight_number} ({buffer_info}, {flight.distance}km): {kits_to_load}")
        
        return load_decisions


# Backwards compatibility
GreedyKitStrategy = PenaltyAwareStrategy
OptimalKitStrategy = PenaltyAwareStrategy
