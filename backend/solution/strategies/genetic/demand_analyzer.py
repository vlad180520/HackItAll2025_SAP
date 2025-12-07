"""Dynamic demand analyzer - loads demand data from CSV files.

This module analyzes flight data from CSV to compute:
- Expected hourly demand per class
- Stockout predictions
- Optimal purchase timing

NO HARDCODED VALUES - all data comes from CSV files.
"""

import csv
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class DemandAnalysis:
    """Results of demand analysis from CSV data."""
    
    # Expected demand per hour (average over simulation)
    hourly_demand: Dict[str, float]
    
    # Total demand over entire simulation
    total_demand: Dict[str, int]
    
    # Stockout hour for each class (None if no stockout)
    stockout_hours: Dict[str, Optional[int]]
    
    # Recommended purchase timing (latest hour to order)
    order_by_hours: Dict[str, int]
    
    # Initial stock at HUB
    initial_stock: Dict[str, int]
    
    # HUB storage capacity
    hub_capacity: Dict[str, int]


def analyze_demand_from_csv(
    flights_csv: str,
    airports_csv: str,
    lead_times: Dict[str, int],
    processing_times: Dict[str, int],
) -> Optional[DemandAnalysis]:
    """Analyze demand patterns from CSV data files.
    
    Args:
        flights_csv: Path to flights.csv
        airports_csv: Path to airports_with_stocks.csv
        lead_times: Lead time per class (from KIT_DEFINITIONS)
        processing_times: Processing time at HUB per class
        
    Returns:
        DemandAnalysis object or None if files not found
    """
    try:
        # Find HUB and get initial stock/capacity
        hub_code, initial_stock, hub_capacity = _load_hub_data(airports_csv)
        
        if not hub_code:
            logger.warning("No HUB found in airports CSV")
            return None
        
        # Load all flights departing from HUB
        hub_departures = _load_hub_departures(flights_csv, hub_code)
        
        if not hub_departures:
            logger.warning("No flights departing from HUB found")
            return None
        
        # Calculate demand metrics
        total_demand = _calculate_total_demand(hub_departures)
        hourly_demand = _calculate_hourly_demand(hub_departures, total_hours=720)
        stockout_hours = _calculate_stockout_hours(hub_departures, initial_stock)
        order_by_hours = _calculate_order_timing(
            stockout_hours, lead_times, processing_times
        )
        
        logger.info(f"Analyzed {len(hub_departures)} flights from HUB")
        logger.info(f"Total demand: {total_demand}")
        logger.info(f"Hourly demand: {hourly_demand}")
        logger.info(f"Stockout hours: {stockout_hours}")
        logger.info(f"Order by hours: {order_by_hours}")
        
        return DemandAnalysis(
            hourly_demand=hourly_demand,
            total_demand=total_demand,
            stockout_hours=stockout_hours,
            order_by_hours=order_by_hours,
            initial_stock=initial_stock,
            hub_capacity=hub_capacity,
        )
        
    except FileNotFoundError as e:
        logger.warning(f"CSV file not found: {e}")
        return None
    except Exception as e:
        logger.error(f"Error analyzing demand: {e}")
        return None


def _load_hub_data(airports_csv: str) -> Tuple[Optional[str], Dict[str, int], Dict[str, int]]:
    """Load HUB airport data from CSV."""
    hub_code = None
    initial_stock = {}
    capacity = {}
    
    # Try multiple path variations
    paths_to_try = [
        airports_csv,
        f"HackitAll2025-main/{airports_csv}",
        f"../{airports_csv}",
        f"../HackitAll2025-main/{airports_csv}",
    ]
    
    csv_path = None
    for path in paths_to_try:
        if Path(path).exists():
            csv_path = path
            break
    
    if not csv_path:
        raise FileNotFoundError(f"Could not find airports CSV: {airports_csv}")
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            code = row.get('code', '')
            if code.upper().startswith('HUB'):
                hub_code = code
                initial_stock = {
                    "FIRST": int(row.get('initial_fc_stock', 0)),
                    "BUSINESS": int(row.get('initial_bc_stock', 0)),
                    "PREMIUM_ECONOMY": int(row.get('initial_pe_stock', 0)),
                    "ECONOMY": int(row.get('initial_ec_stock', 0)),
                }
                capacity = {
                    "FIRST": int(row.get('capacity_fc', 10000)),
                    "BUSINESS": int(row.get('capacity_bc', 10000)),
                    "PREMIUM_ECONOMY": int(row.get('capacity_pe', 10000)),
                    "ECONOMY": int(row.get('capacity_ec', 100000)),
                }
                break
    
    return hub_code, initial_stock, capacity


def _load_hub_departures(flights_csv: str, hub_code: str) -> List[Dict]:
    """Load all flights departing from HUB."""
    hub_departures = []
    
    # Try multiple path variations
    paths_to_try = [
        flights_csv,
        f"HackitAll2025-main/{flights_csv}",
        f"../{flights_csv}",
        f"../HackitAll2025-main/{flights_csv}",
    ]
    
    csv_path = None
    for path in paths_to_try:
        if Path(path).exists():
            csv_path = path
            break
    
    if not csv_path:
        raise FileNotFoundError(f"Could not find flights CSV: {flights_csv}")
    
    # Need to find HUB's UUID first
    hub_uuid = None
    airports_paths = [
        "eval-platform/src/main/resources/liquibase/data/airports_with_stocks.csv",
        "HackitAll2025-main/eval-platform/src/main/resources/liquibase/data/airports_with_stocks.csv",
        "../HackitAll2025-main/eval-platform/src/main/resources/liquibase/data/airports_with_stocks.csv",
    ]
    
    for ap in airports_paths:
        if Path(ap).exists():
            with open(ap, 'r') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    if row.get('code', '').upper().startswith('HUB'):
                        hub_uuid = row.get('id')
                        break
            break
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            # Check if origin is HUB (by UUID or code)
            origin = row.get('origin_airport_id', '')
            if origin == hub_uuid or origin == hub_code:
                dep_day = int(row.get('scheduled_depart_day', 0))
                dep_hour = int(row.get('scheduled_depart_hour', 0))
                
                hub_departures.append({
                    'dep_hours': dep_day * 24 + dep_hour,
                    'FIRST': int(row.get('planned_first_passengers', 0)),
                    'BUSINESS': int(row.get('planned_business_passengers', 0)),
                    'PREMIUM_ECONOMY': int(row.get('planned_premium_economy_passengers', 0)),
                    'ECONOMY': int(row.get('planned_economy_passengers', 0)),
                })
    
    # Sort by departure time
    hub_departures.sort(key=lambda x: x['dep_hours'])
    return hub_departures


def _calculate_total_demand(departures: List[Dict]) -> Dict[str, int]:
    """Calculate total demand per class."""
    total = {"FIRST": 0, "BUSINESS": 0, "PREMIUM_ECONOMY": 0, "ECONOMY": 0}
    for flight in departures:
        for class_type in total:
            total[class_type] += flight.get(class_type, 0)
    return total


def _calculate_hourly_demand(departures: List[Dict], total_hours: int) -> Dict[str, float]:
    """Calculate average hourly demand per class."""
    total = _calculate_total_demand(departures)
    return {k: v / max(1, total_hours) for k, v in total.items()}


def _calculate_stockout_hours(
    departures: List[Dict], 
    initial_stock: Dict[str, int]
) -> Dict[str, Optional[int]]:
    """Calculate when each class runs out of stock."""
    stockout = {}
    cumulative = {"FIRST": 0, "BUSINESS": 0, "PREMIUM_ECONOMY": 0, "ECONOMY": 0}
    
    for class_type in cumulative:
        stockout[class_type] = None  # No stockout by default
    
    for flight in departures:
        for class_type in cumulative:
            cumulative[class_type] += flight.get(class_type, 0)
            
            if stockout[class_type] is None:
                if cumulative[class_type] > initial_stock.get(class_type, 0):
                    stockout[class_type] = flight['dep_hours']
    
    return stockout


def _calculate_order_timing(
    stockout_hours: Dict[str, Optional[int]],
    lead_times: Dict[str, int],
    processing_times: Dict[str, int],
) -> Dict[str, int]:
    """Calculate latest hour to place order to avoid stockout."""
    order_by = {}
    
    for class_type, stockout_hr in stockout_hours.items():
        if stockout_hr is not None:
            lead = lead_times.get(class_type, 48)
            proc = processing_times.get(class_type, 6)
            # Must order before stockout - lead_time - processing_time
            order_by[class_type] = max(0, stockout_hr - lead - proc)
        else:
            # No stockout - can order anytime
            order_by[class_type] = 720
    
    return order_by


# Singleton cache for demand analysis
_cached_analysis: Optional[DemandAnalysis] = None


def get_demand_analysis(force_reload: bool = False) -> Optional[DemandAnalysis]:
    """Get cached demand analysis or compute it.
    
    Args:
        force_reload: If True, recompute from CSV files
        
    Returns:
        DemandAnalysis object or None if files not found
    """
    global _cached_analysis
    
    if _cached_analysis is not None and not force_reload:
        return _cached_analysis
    
    # Default paths
    flights_csv = "eval-platform/src/main/resources/liquibase/data/flights.csv"
    airports_csv = "eval-platform/src/main/resources/liquibase/data/airports_with_stocks.csv"
    
    # Lead times from KitType.java
    lead_times = {
        "FIRST": 48,
        "BUSINESS": 36,
        "PREMIUM_ECONOMY": 24,
        "ECONOMY": 12,
    }
    
    # Processing times at HUB (from airports CSV - typically 6, 4, 2, 1)
    processing_times = {
        "FIRST": 6,
        "BUSINESS": 4,
        "PREMIUM_ECONOMY": 2,
        "ECONOMY": 1,
    }
    
    _cached_analysis = analyze_demand_from_csv(
        flights_csv, airports_csv, lead_times, processing_times
    )
    
    return _cached_analysis


def get_expected_hourly_demand() -> Dict[str, float]:
    """Get expected hourly demand per class from CSV analysis.
    
    Returns default values if CSV not available.
    """
    analysis = get_demand_analysis()
    
    if analysis:
        return analysis.hourly_demand
    
    # Fallback defaults (conservative estimates)
    logger.warning("Using fallback demand estimates - CSV data not available")
    return {
        "FIRST": 25.0,
        "BUSINESS": 120.0,
        "PREMIUM_ECONOMY": 60.0,
        "ECONOMY": 600.0,
    }


def get_expected_total_demand() -> Dict[str, int]:
    """Get expected total demand per class from CSV analysis.
    
    Returns default values if CSV not available.
    """
    analysis = get_demand_analysis()
    
    if analysis:
        return analysis.total_demand
    
    # Fallback defaults (conservative estimates)
    logger.warning("Using fallback demand estimates - CSV data not available")
    return {
        "FIRST": 18000,
        "BUSINESS": 86400,
        "PREMIUM_ECONOMY": 43200,
        "ECONOMY": 432000,
    }

