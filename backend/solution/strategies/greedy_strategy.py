"""Greedy strategy implementation for kit management."""

import logging
from typing import Dict, List, Tuple

from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.airport import Airport
from models.aircraft import AircraftType
from solution.config import SolutionConfig

logger = logging.getLogger(__name__)


class GreedyPurchaseStrategy:
    """Greedy strategy for purchasing kits."""
    
    def __init__(self, config: SolutionConfig):
        """Initialize purchase strategy."""
        self.config = config
    
    def decide_purchases(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
    ) -> List[KitPurchaseOrder]:
        """
        OPTIMIZED HUB PURCHASE: Only buy at HUB1 when stock is low.
        
        KEY RULES:
        1. ONLY purchase at HUB1 (main hub)
        2. Purchase when stock < 30% of capacity
        3. Target 80% of capacity after purchase
        """
        purchases = []
        
        # CRITICAL: Only HUB1 can order new kits!
        HUB_CODE = "HUB1"
        
        if HUB_CODE not in airports:
            logger.error(f"HUB1 not found in airports!")
            return purchases
        
        hub = airports[HUB_CODE]
        current_inventory = state.inventory.get(HUB_CODE, {})
        
        # Check each kit class
        for class_type in ["first", "business", "premium_economy", "economy"]:
            current_stock = current_inventory.get(class_type, 0)
            capacity = hub.storage_capacity.get(class_type, 0)
            
            if capacity <= 0:
                continue
            
            # Calculate thresholds
            reorder_threshold = int(capacity * self.config.HUB_REORDER_THRESHOLD)
            target_level = int(capacity * self.config.HUB_TARGET_LEVEL)
            
            # Check if we need to reorder
            if current_stock < reorder_threshold:
                # Calculate purchase quantity to reach target
                quantity = target_level - current_stock
                
                if quantity > 0:
                    purchases.append(KitPurchaseOrder(
                        airport=HUB_CODE,
                        class_type=class_type,
                        quantity=quantity,
                        execution_time=state.current_time
                    ))
                    
                    logger.info(
                        f"HUB PURCHASE: {class_type.upper()} x{quantity} "
                        f"(stock: {current_stock}/{capacity}, threshold: {reorder_threshold}, "
                        f"target: {target_level})"
                    )
        
        # Calculate predicted demand for validation
        upcoming_demand = self._calculate_demand(flights, state.current_time)
        hub_demand = upcoming_demand.get(HUB_CODE, {})
        
        for class_type, demand in hub_demand.items():
            current = current_inventory.get(class_type, 0)
            if current < demand:
                logger.warning(
                    f"HUB1 {class_type.upper()}: Current stock {current} < predicted demand {demand}"
                )
        
        return purchases
    
    def _calculate_demand(
        self, 
        flights: List[Flight], 
        current_time: ReferenceHour = None
    ) -> Dict[str, Dict[str, int]]:
        """
        Calculate demand based on upcoming flights.
        
        Args:
            flights: List of upcoming flights
            current_time: Current simulation time (for filtering)
        
        Returns:
            Dict mapping airport_code -> {class_type: demand}
        """
        demand = {}
        
        # Consider flights in lookahead window
        lookahead_count = min(len(flights), self.config.LOOKAHEAD_HOURS * 10)  # ~10 flights per hour
        
        for flight in flights[:lookahead_count]:
            origin = flight.origin
            if origin not in demand:
                demand[origin] = {}
            
            for class_type, count in flight.passengers.items():
                if count > 0:
                    if class_type not in demand[origin]:
                        demand[origin][class_type] = 0
                    
                    # Add passenger count + safety buffer
                    buffer = max(
                        int(count * self.config.PASSENGER_BUFFER_PERCENT),
                        self.config.MIN_BUFFER_KITS
                    )
                    demand[origin][class_type] += count + buffer
        
        return demand


class GreedyLoadingStrategy:
    """Greedy strategy for loading kits."""
    
    def __init__(self, config: SolutionConfig):
        """Initialize loading strategy."""
        self.config = config
    
    def decide_loading(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ) -> List[KitLoadDecision]:
        """
        OPTIMIZED SAFE LOADING: Load passengers + buffer to avoid penalties.
        
        KEY RULES:
        1. ALWAYS load more than passengers (buffer)
        2. NEVER exceed aircraft capacity
        3. NEVER exceed available stock (will cause understock penalty)
        """
        load_decisions = []
        
        for flight in flights:
            if flight.origin not in state.inventory:
                logger.warning(f"No inventory data for origin {flight.origin}")
                continue
            
            inventory = state.inventory[flight.origin].copy()
            aircraft_type = aircraft_types.get(flight.aircraft_type)
            
            if not aircraft_type:
                logger.warning(f"Unknown aircraft type: {flight.aircraft_type}")
                continue
            
            # Calculate kits to load for each class
            kits_to_load = {}
            
            for class_type, passengers in flight.passengers.items():
                if passengers <= 0:
                    continue
                
                # Calculate buffer: 15% + minimum 2 kits
                buffer = max(
                    int(passengers * self.config.PASSENGER_BUFFER_PERCENT),
                    self.config.MIN_BUFFER_KITS
                )
                buffer = min(buffer, self.config.MAX_BUFFER_KITS)
                
                # Total needed = passengers + buffer
                needed = passengers + buffer
                
                # Check aircraft capacity - CRITICAL!
                capacity = aircraft_type.kit_capacity.get(class_type, 0)
                if capacity <= 0:
                    logger.warning(f"No capacity for {class_type} on {flight.aircraft_type}")
                    continue
                
                # Don't exceed capacity
                needed = min(needed, capacity)
                
                # Check available stock
                available = inventory.get(class_type, 0)
                
                if available < passengers:
                    # CRITICAL: Not enough for passengers - load what we have
                    logger.error(
                        f"INSUFFICIENT STOCK! Flight {flight.flight_id} needs {passengers} {class_type}, "
                        f"only {available} available at {flight.origin}"
                    )
                    kits_to_load[class_type] = available
                elif available < needed:
                    # Enough for passengers but not full buffer
                    logger.warning(
                        f"Limited buffer: Flight {flight.flight_id} wants {needed} {class_type}, "
                        f"only {available} available at {flight.origin}"
                    )
                    kits_to_load[class_type] = available
                else:
                    # Perfect: enough for passengers + buffer
                    kits_to_load[class_type] = needed
                    logger.debug(
                        f"Loading {needed} {class_type} kits for {passengers} passengers "
                        f"(buffer: {buffer}) on flight {flight.flight_id}"
                    )
            
            if kits_to_load:
                load_decisions.append(KitLoadDecision(
                    flight_id=flight.flight_id,
                    kits_per_class=kits_to_load,
                    execution_time=ReferenceHour(
                        day=flight.departure_time.day,
                        hour=flight.departure_time.hour
                    )
                ))
                
                logger.debug(f"Load decision: {flight.flight_id} - {kits_to_load}")
        
        return load_decisions


class GreedyKitStrategy:
    """
    Complete greedy strategy combining purchase and loading.
    
    PUNCT DE START pentru modificări! 
    Această clasă combină strategiile de purchase și loading.
    """
    
    def __init__(self, config: SolutionConfig):
        """Initialize greedy strategy."""
        self.config = config
        self.purchase_strategy = GreedyPurchaseStrategy(config)
        self.loading_strategy = GreedyLoadingStrategy(config)
        logger.info(f"Initialized GreedyKitStrategy with config: {config.to_dict()}")
    
    def optimize(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """
        Main optimization method.
        
        MODIFICĂ ACEST WORKFLOW pentru a schimba comportamentul complet!
        """
        logger.info(f"Running greedy optimization for round {state.current_round}")
        
        # Step 1: Decide on purchases
        purchases = self.purchase_strategy.decide_purchases(state, flights, airports)
        
        # Step 2: Decide on loading
        loads = self.loading_strategy.decide_loading(state, flights, airports, aircraft_types)
        
        logger.info(f"Generated {len(purchases)} purchases and {len(loads)} loads")
        
        return loads, purchases
