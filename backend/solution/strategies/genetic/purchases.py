"""Purchase computation for genetic algorithm.

Implements "buy when needed" logic:
- For HUB classes, if projected demand within horizon exceeds current stock, buy the shortfall
- Capacity-clamped purchases only
- NO comparison of "min(buying, penalty)" - just buy what's needed

Purchase horizon and buffers are configured in GeneticConfig.
"""

from typing import Dict, List
from collections import defaultdict

from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.airport import Airport
from models.kit import KitPurchaseOrder
from config import CLASS_TYPES, KIT_DEFINITIONS

from solution.strategies.genetic.config import GeneticConfig
from solution.strategies.genetic.precompute import find_hub


def compute_purchase_genes_simple(
    ga_config: GeneticConfig,
    state: GameState,
    flights: List[Flight],
    airports: Dict[str, Airport],
    now_hours: int,
) -> Dict[str, int]:
    """Compute purchase quantities using buy-when-needed logic.
    
    Algorithm:
    1. For each class at HUB, compute demand within purchase_horizon_hours
    2. Only count flights where departure >= ETA (lead_time + proc_time)
    3. Target = demand * buffer (default 1.05)
    4. Purchase = min(target - stock, capacity - stock)
    5. If stock >= target, purchase = 0
    
    No penalty comparison - just buy what's needed to cover demand.
    
    Args:
        ga_config: Genetic algorithm configuration
        state: Current game state
        flights: List of all flights
        airports: Airport dictionary
        now_hours: Current time in hours
        
    Returns:
        Dictionary mapping class to purchase quantity
    """
    purchase_genes = {}
    
    # Find HUB
    hub_code, hub_airport = find_hub(airports)
    
    if not hub_code or not hub_airport:
        return {c: 0 for c in CLASS_TYPES}
    
    hub_inventory = state.airport_inventories.get(hub_code, {})
    horizon_end = now_hours + ga_config.purchase_horizon_hours
    buffer = ga_config.purchase_buffer  # Default 1.05 (5% buffer)
    
    for class_type in CLASS_TYPES:
        stock = hub_inventory.get(class_type, 0)
        capacity = hub_airport.storage_capacity.get(class_type, 1000)
        
        # Calculate ETA for this class
        lead_time = int(KIT_DEFINITIONS[class_type]["lead_time"])
        processing_time = hub_airport.processing_times.get(class_type, 0)
        eta_hours = now_hours + lead_time + processing_time
        
        # Sum demand from flights departing from HUB where dep >= ETA and dep < horizon_end
        demand = 0
        for flight in flights:
            if flight.origin == hub_code:
                dep_hours = flight.scheduled_departure.to_hours()
                if eta_hours <= dep_hours < horizon_end:
                    demand += flight.planned_passengers.get(class_type, 0)
        
        # Target stock = demand * buffer
        target = int(demand * buffer)
        
        # Buy when needed: if stock < target, buy the shortfall
        if stock < target and demand > 0:
            needed = target - stock
            # Capacity clamp: can't exceed capacity - stock
            max_purchase = max(0, capacity - stock)
            purchase = min(needed, max_purchase)
            purchase_genes[class_type] = max(0, purchase)
        else:
            purchase_genes[class_type] = 0
    
    return purchase_genes


def compute_purchase_genes_minimal(
    ga_config: GeneticConfig,
    state: GameState,
    flights: List[Flight],
    airports: Dict[str, Airport],
    now_hours: int,
) -> Dict[str, int]:
    """Compute minimal purchase quantities - conservative approach.
    
    Same algorithm as simple but with:
    - Smaller buffer (1.02 = 2%)
    - Shorter horizon (36h instead of 60h)
    
    This is for conservative individuals that minimize purchasing.
    """
    purchase_genes = {}
    
    # Find HUB
    hub_code, hub_airport = find_hub(airports)
    
    if not hub_code or not hub_airport:
        return {c: 0 for c in CLASS_TYPES}
    
    hub_inventory = state.airport_inventories.get(hub_code, {})
    horizon_end = now_hours + ga_config.minimal_horizon_hours  # 36h
    buffer = ga_config.purchase_buffer_minimal  # 1.02 (2% buffer)
    
    for class_type in CLASS_TYPES:
        stock = hub_inventory.get(class_type, 0)
        capacity = hub_airport.storage_capacity.get(class_type, 1000)
        
        # Calculate ETA
        lead_time = int(KIT_DEFINITIONS[class_type]["lead_time"])
        processing_time = hub_airport.processing_times.get(class_type, 0)
        eta_hours = now_hours + lead_time + processing_time
        
        # Sum demand only for flights within shorter horizon
        demand = 0
        for flight in flights:
            if flight.origin == hub_code:
                dep_hours = flight.scheduled_departure.to_hours()
                if eta_hours <= dep_hours < horizon_end:
                    demand += flight.planned_passengers.get(class_type, 0)
        
        # Minimal target
        target = int(demand * buffer)
        
        # Only purchase if critically needed
        if stock < target * 0.9 and demand > 0:  # 90% threshold for minimal
            needed = target - stock
            max_purchase = max(0, capacity - stock)
            purchase = min(needed, max_purchase)
            purchase_genes[class_type] = max(0, purchase)
        else:
            purchase_genes[class_type] = 0
    
    return purchase_genes


def compute_purchases_heuristic(
    ga_config: GeneticConfig,
    state: GameState,
    flights: List[Flight],
    airports: Dict[str, Airport],
    now_hours: int,
) -> List[KitPurchaseOrder]:
    """Compute purchases using heuristic when no flights to load.
    
    If no loading flights are present, buy to cover next 24h HUB demand
    with a 5% buffer, capacity-clamped.
    
    Args:
        ga_config: Genetic algorithm configuration
        state: Current game state
        flights: List of all flights
        airports: Airport dictionary
        now_hours: Current time in hours
        
    Returns:
        List of KitPurchaseOrder (empty or single order)
    """
    hub_code, hub_airport = find_hub(airports)
    
    if not hub_code or not hub_airport:
        return []
    
    hub_inventory = state.airport_inventories.get(hub_code, {})
    
    # 24-hour horizon for heuristic purchases
    horizon_end = now_hours + 24
    buffer = 1.05  # 5% buffer
    
    kits_per_class = {}
    max_eta_hours = 0
    
    for class_type in CLASS_TYPES:
        stock = hub_inventory.get(class_type, 0)
        capacity = hub_airport.storage_capacity.get(class_type, 1000)
        
        # Calculate ETA
        lead_time = int(KIT_DEFINITIONS[class_type]["lead_time"])
        processing_time = hub_airport.processing_times.get(class_type, 0)
        eta_hours = now_hours + lead_time + processing_time
        max_eta_hours = max(max_eta_hours, lead_time + processing_time)
        
        # Count viable demand (flights after ETA)
        demand = 0
        for flight in flights:
            if flight.origin == hub_code:
                dep_hours = flight.scheduled_departure.to_hours()
                if eta_hours <= dep_hours < horizon_end:
                    demand += flight.planned_passengers.get(class_type, 0)
        
        # Buy when needed with 5% buffer
        target = int(demand * buffer)
        
        if stock < target and demand > 0:
            needed = target - stock
            max_purchase = max(0, capacity - stock)
            purchase = min(needed, max_purchase)
            if purchase > 0:
                kits_per_class[class_type] = purchase
    
    if not kits_per_class:
        return []
    
    # Calculate expected delivery
    current_time = ReferenceHour(day=state.current_day, hour=state.current_hour)
    delivery_hours = now_hours + max_eta_hours
    delivery_day = delivery_hours // 24
    delivery_hour = delivery_hours % 24
    
    expected_delivery = ReferenceHour(
        day=delivery_day,
        hour=delivery_hour
    )
    
    return [KitPurchaseOrder(
        kits_per_class=kits_per_class,
        order_time=current_time,
        expected_delivery=expected_delivery
    )]

