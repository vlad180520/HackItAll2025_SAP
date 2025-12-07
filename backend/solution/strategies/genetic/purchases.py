"""Purchase computation for genetic algorithm.

Implements proactive purchasing logic:
- For HUB classes, compute projected demand over multiple horizons
- Purchase to maintain a safety stock buffer
- Use longer-term demand forecasting to avoid stockouts
- Consider rate of consumption vs stock levels

Purchase horizon and buffers are configured in GeneticConfig.
"""

import logging
from typing import Dict, List
from collections import defaultdict

from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.airport import Airport
from models.kit import KitPurchaseOrder
from config import CLASS_TYPES, KIT_DEFINITIONS

from solution.strategies.genetic.config import GeneticConfig
from solution.strategies.genetic.precompute import find_hub
from solution.strategies.genetic.demand_analyzer import (
    get_expected_hourly_demand,
    get_expected_total_demand,
)

logger = logging.getLogger(__name__)

# API validation limits for purchases (from PerClassAmount.java)
# CRITICAL: The API will reject requests exceeding these limits!
API_PURCHASE_LIMITS = {
    "FIRST": 42000,
    "BUSINESS": 42000,
    "PREMIUM_ECONOMY": 1000,  # Note: Much lower than other classes!
    "ECONOMY": 42000,
}


def compute_purchase_genes_simple(
    ga_config: GeneticConfig,
    state: GameState,
    flights: List[Flight],
    airports: Dict[str, Airport],
    now_hours: int,
) -> Dict[str, int]:
    """Compute purchase quantities using AGGRESSIVE proactive purchasing.
    
    CRITICAL DATA FROM CSV ANALYSIS:
    - FIRST: Stockout hour 47, lead+proc=54h → MUST order at hour 0!
    - BUSINESS: Stockout hour 37, lead+proc=40h → MUST order at hour 0!
    - PREMIUM_ECONOMY: Stockout hour 35, lead+proc=26h → Order by hour 9
    - ECONOMY: Stockout hour 31, lead+proc=13h → Order by hour 18
    
    Strategy: Order IMMEDIATELY and ALWAYS if stock won't cover demand until ETA.
    
    Args:
        ga_config: Genetic algorithm configuration
        state: Current game state
        flights: List of ALL visible flights
        airports: Airport dictionary
        now_hours: Current time in hours
        
    Returns:
        Dictionary mapping class to purchase quantity
    """
    purchase_genes = {}
    
    # Find HUB
    hub_code, hub_airport = find_hub(airports)
    
    if not hub_code or not hub_airport:
        logger.warning("No HUB found - cannot compute purchases")
        return {c: 0 for c in CLASS_TYPES}
    
    hub_inventory = state.airport_inventories.get(hub_code, {})
    
    # Log analysis
    hub_outbound_count = sum(1 for f in flights if f.origin == hub_code)
    has_flight_data = hub_outbound_count > 0
    logger.info(f"Purchase analysis at hour {now_hours}: {len(flights)} flights, {hub_outbound_count} from HUB")
    
    for class_type in CLASS_TYPES:
        stock = hub_inventory.get(class_type, 0)
        capacity = hub_airport.storage_capacity.get(class_type, 1000)
        
        # Get lead time and processing time
        lead_time = int(KIT_DEFINITIONS[class_type]["lead_time"])
        processing_time = hub_airport.processing_times.get(class_type, 0)
        eta_hours = now_hours + lead_time + processing_time
        
        if has_flight_data:
            # Use actual flight data
            demand_until_eta = _compute_hub_outbound_demand(flights, hub_code, now_hours, eta_hours, class_type)
            demand_24h = _compute_hub_outbound_demand(flights, hub_code, now_hours, now_hours + 24, class_type)
            demand_48h = _compute_hub_outbound_demand(flights, hub_code, now_hours, now_hours + 48, class_type)
            demand_72h = _compute_hub_outbound_demand(flights, hub_code, now_hours, now_hours + 72, class_type)
            demand_168h = _compute_hub_outbound_demand(flights, hub_code, now_hours, now_hours + 168, class_type)
            demand_after_eta = _compute_hub_outbound_demand(flights, hub_code, eta_hours, now_hours + 720, class_type)
        else:
            # FALLBACK: No flights yet (round 0) - use expected demand from CSV
            hourly_demand = get_expected_hourly_demand()
            hourly = hourly_demand.get(class_type, 25.0)
            demand_until_eta = int(hourly * (eta_hours - now_hours))
            demand_24h = int(hourly * 24)
            demand_48h = int(hourly * 48)
            demand_72h = int(hourly * 72)
            demand_168h = int(hourly * 168)
            demand_after_eta = int(hourly * (720 - eta_hours))
            logger.info(f"Using expected demand fallback for {class_type}: hourly={hourly}")
        
        # Stock projection at ETA (when order arrives)
        stock_at_eta = stock - demand_until_eta
        
        # AGGRESSIVE PURCHASE TRIGGERS:
        # 1. Stock will go negative before order arrives (CRITICAL!)
        # 2. Stock at ETA < 50% of 48h demand after ETA (proactive)
        # 3. Current stock < 168h demand (long-term planning)
        # 4. Stock ratio < 1.3 (very proactive)
        
        demand_48h_after_eta = _compute_hub_outbound_demand(
            flights, hub_code, eta_hours, eta_hours + 48, class_type
        )
        
        should_purchase = (
            stock_at_eta < 0 or  # CRITICAL: will stockout before order arrives
            stock_at_eta < (demand_48h_after_eta * 0.5) or  # Low safety margin at ETA
            stock < demand_168h or  # Won't cover 168h demand
            (demand_168h > 0 and stock / max(1, demand_168h) < 1.3) or  # Ratio too low (safe div)
            (now_hours < 24 and demand_after_eta > 0)  # Early game: always buy if future demand exists
        )
        
        # Calculate purchase amount
        if should_purchase and (demand_after_eta > 0 or demand_168h > 0):
            # Target: cover demand after ETA with buffer, compensate for any negative at ETA
            shortfall_at_eta = max(0, -stock_at_eta)  # How much we'll be short
            
            # Need: demand after ETA + shortfall + 30% safety buffer
            target = int((demand_after_eta + shortfall_at_eta) * 1.3)
            
            # Also ensure we cover 168h with buffer
            target = max(target, int(demand_168h * 1.2))
            
            needed = max(0, target - stock)
            max_purchase = max(0, capacity - stock)
            purchase = min(needed, max_purchase)
            purchase_genes[class_type] = max(0, purchase)
            
            logger.info(
                f"PURCHASE {class_type}: stock={stock}, stock_at_eta={stock_at_eta}, "
                f"shortfall={shortfall_at_eta}, d_until_eta={demand_until_eta}, d_after_eta={demand_after_eta}, "
                f"d168h={demand_168h}, target={target}, purchase={purchase}, capacity={capacity}"
            )
        else:
            purchase_genes[class_type] = 0
            logger.debug(
                f"NO PURCHASE {class_type}: stock={stock}, stock_at_eta={stock_at_eta}, "
                f"d_until_eta={demand_until_eta}, d_after_eta={demand_after_eta}, d168h={demand_168h}"
            )
    
    # Clamp to API limits (CRITICAL: API rejects purchases exceeding these!)
    for class_type in purchase_genes:
        api_limit = API_PURCHASE_LIMITS.get(class_type, 42000)
        if purchase_genes[class_type] > api_limit:
            logger.warning(
                f"Clamping {class_type} purchase from {purchase_genes[class_type]} to API limit {api_limit}"
            )
            purchase_genes[class_type] = api_limit
    
    total_purchase = sum(purchase_genes.values())
    if total_purchase > 0:
        logger.info(f"TOTAL PURCHASE ORDER: {purchase_genes}")
    
    return purchase_genes


def _compute_hub_outbound_demand(
    flights: List[Flight],
    hub_code: str,
    start_hours: int,
    end_hours: int,
    class_type: str,
) -> int:
    """Compute demand for flights departing from HUB in time window."""
    demand = 0
    for flight in flights:
        if flight.origin == hub_code:
            dep_hours = flight.scheduled_departure.to_hours()
            if start_hours <= dep_hours < end_hours:
                demand += flight.planned_passengers.get(class_type, 0)
    return demand


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
    
    CRITICAL FIX: At round 0, there are NO flights in flight_history yet!
    Use expected demand from CSV analysis as fallback.
    
    Args:
        ga_config: Genetic algorithm configuration
        state: Current game state
        flights: List of all flights (may be empty at round 0!)
        airports: Airport dictionary
        now_hours: Current time in hours
        
    Returns:
        List of KitPurchaseOrder (empty or single order)
    """
    hub_code, hub_airport = find_hub(airports)
    
    if not hub_code or not hub_airport:
        logger.warning("No HUB found for heuristic purchases")
        return []
    
    hub_inventory = state.airport_inventories.get(hub_code, {})
    
    kits_per_class = {}
    max_eta_hours = 0
    
    # Check if we have flight data
    hub_flights = [f for f in flights if f.origin == hub_code]
    has_flight_data = len(hub_flights) > 0
    
    logger.info(f"Heuristic purchase at hour {now_hours}: {len(flights)} flights, {len(hub_flights)} from HUB")
    
    for class_type in CLASS_TYPES:
        stock = hub_inventory.get(class_type, 0)
        capacity = hub_airport.storage_capacity.get(class_type, 1000)
        
        # Calculate ETA
        lead_time = int(KIT_DEFINITIONS[class_type]["lead_time"])
        processing_time = hub_airport.processing_times.get(class_type, 0)
        eta_hours = now_hours + lead_time + processing_time
        max_eta_hours = max(max_eta_hours, lead_time + processing_time)
        
        if has_flight_data:
            # Use actual flight data
            demand = _compute_hub_outbound_demand(flights, hub_code, eta_hours, now_hours + 168, class_type)
            demand_until_eta = _compute_hub_outbound_demand(flights, hub_code, now_hours, eta_hours, class_type)
        else:
            # FALLBACK: No flights yet (round 0) - use expected demand from CSV
            # Calculate expected demand for the period after ETA
            hourly_demand = get_expected_hourly_demand()
            hourly = hourly_demand.get(class_type, 25.0)
            hours_after_eta = 720 - eta_hours  # Remaining hours in simulation
            demand = int(hourly * min(hours_after_eta, 168))
            demand_until_eta = int(hourly * (eta_hours - now_hours))
            logger.info(f"Using expected demand fallback for {class_type}: {demand} (no flight data)")
        
        # Calculate stock at ETA
        stock_at_eta = stock - demand_until_eta
        
        # AGGRESSIVE: Buy if stock_at_eta < 0 OR if we won't cover demand
        if stock_at_eta < 0 or stock < demand:
            shortfall = max(0, -stock_at_eta)
            target = int((demand + shortfall) * 1.3)  # 30% buffer
            needed = max(0, target - stock)
            max_purchase = max(0, capacity - stock)
            purchase = min(needed, max_purchase)
            
            if purchase > 0:
                kits_per_class[class_type] = purchase
                logger.info(
                    f"HEURISTIC PURCHASE {class_type}: stock={stock}, stock_at_eta={stock_at_eta}, "
                    f"demand={demand}, target={target}, purchase={purchase}"
                )
    
    if not kits_per_class:
        logger.info("No heuristic purchases needed")
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
    
    # Clamp to API limits (CRITICAL: API rejects purchases exceeding these!)
    for class_type in list(kits_per_class.keys()):
        api_limit = API_PURCHASE_LIMITS.get(class_type, 42000)
        if kits_per_class[class_type] > api_limit:
            logger.warning(
                f"Clamping {class_type} purchase from {kits_per_class[class_type]} to API limit {api_limit}"
            )
            kits_per_class[class_type] = api_limit
    
    logger.info(f"HEURISTIC TOTAL ORDER: {kits_per_class}")
    
    return [KitPurchaseOrder(
        kits_per_class=kits_per_class,
        order_time=current_time,
        expected_delivery=expected_delivery
    )]

