"""Data loader module for parsing CSV files."""

import logging
import pandas as pd
from typing import Dict
from pathlib import Path
import os

from .models.airport import Airport
from .models.aircraft import AircraftType
from .config import Config, CLASS_TYPES

logger = logging.getLogger(__name__)


def _resolve_csv_path(csv_path: str) -> str:
    """
    Resolve CSV path, trying both with and without HackitAll2025-main prefix.
    
    Args:
        csv_path: Path to CSV file
        
    Returns:
        Resolved path that exists
    """
    # If path already exists, use it
    if os.path.exists(csv_path):
        return csv_path
    
    # Try with HackitAll2025-main prefix
    prefixed_path = f"HackitAll2025-main/{csv_path}"
    if os.path.exists(prefixed_path):
        return prefixed_path
    
    # Return original path (will raise FileNotFoundError if doesn't exist)
    return csv_path


def load_airports(csv_path: str, config: Config) -> Dict[str, Airport]:
    """
    Parse airports_with_stocks.csv and produce Airport instances.
    
    Args:
        csv_path: Path to airports CSV file
        config: Configuration object with defaults
        
    Returns:
        Dictionary mapping airport code to Airport instance
    """
    airports = {}
    
    try:
        # Resolve path (handle both with and without HackitAll2025-main prefix)
        resolved_path = _resolve_csv_path(csv_path)
        # CSV uses semicolon separator
        df = pd.read_csv(resolved_path, sep=';')
        logger.info(f"Loaded airports CSV with {len(df)} rows")
        
        # Expected columns (with conservative defaults if missing)
        required_cols = ["code", "name"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        for _, row in df.iterrows():
            code = str(row["code"])
            name = str(row.get("name", code))
            # Check if it's a hub (HUB1, HUB, or is_hub column)
            is_hub = code.upper().startswith("HUB") or bool(row.get("is_hub", False))
            
            # Parse per-class data with defaults
            # CSV uses abbreviations: fc, bc, pe, ec
            storage_capacity = {}
            loading_costs = {}
            processing_costs = {}
            processing_times = {}
            current_inventory = {}
            
            # Map class types to CSV column abbreviations
            class_abbrev = {
                "FIRST": "fc",
                "BUSINESS": "bc",
                "PREMIUM_ECONOMY": "pe",
                "ECONOMY": "ec"
            }
            
            for class_type in CLASS_TYPES:
                abbrev = class_abbrev[class_type]
                
                # Storage capacity (capacity_fc, capacity_bc, etc.)
                cap_col = f"capacity_{abbrev}"
                storage_capacity[class_type] = int(row.get(cap_col, config.DEFAULT_STORAGE_CAPACITY))
                
                # Loading costs (first_loading_cost, business_loading_cost, etc.)
                load_col = f"{abbrev}_loading_cost" if abbrev != "fc" else "first_loading_cost"
                if abbrev == "fc":
                    load_col = "first_loading_cost"
                elif abbrev == "bc":
                    load_col = "business_loading_cost"
                elif abbrev == "pe":
                    load_col = "premium_economy_loading_cost"
                else:  # ec
                    load_col = "economy_loading_cost"
                loading_costs[class_type] = float(row.get(load_col, config.DEFAULT_LOADING_COST))
                
                # Processing costs (first_processing_cost, business_processing_cost, etc.)
                if abbrev == "fc":
                    proc_cost_col = "first_processing_cost"
                elif abbrev == "bc":
                    proc_cost_col = "business_processing_cost"
                elif abbrev == "pe":
                    proc_cost_col = "premium_economy_processing_cost"
                else:  # ec
                    proc_cost_col = "economy_processing_cost"
                processing_costs[class_type] = float(row.get(proc_cost_col, config.DEFAULT_PROCESSING_COST))
                
                # Processing times (first_processing_time, business_processing_time, etc.)
                if abbrev == "fc":
                    proc_time_col = "first_processing_time"
                elif abbrev == "bc":
                    proc_time_col = "business_processing_time"
                elif abbrev == "pe":
                    proc_time_col = "premium_economy_processing_time"
                else:  # ec
                    proc_time_col = "economy_processing_time"
                processing_times[class_type] = int(row.get(proc_time_col, config.DEFAULT_PROCESSING_TIME))
                
                # Initial inventory (initial_fc_stock, initial_bc_stock, etc.)
                if abbrev == "fc":
                    inv_col = "initial_fc_stock"
                elif abbrev == "bc":
                    inv_col = "initial_bc_stock"
                elif abbrev == "pe":
                    inv_col = "initial_pe_stock"
                else:  # ec
                    inv_col = "initial_ec_stock"
                default_inv = config.DEFAULT_HUB_INVENTORY if is_hub else config.DEFAULT_OUTSTATION_INVENTORY
                current_inventory[class_type] = int(row.get(inv_col, default_inv))
            
            airport = Airport(
                code=code,
                name=name,
                is_hub=is_hub,
                storage_capacity=storage_capacity,
                loading_costs=loading_costs,
                processing_costs=processing_costs,
                processing_times=processing_times,
                current_inventory=current_inventory,
            )
            airports[code] = airport
            
    except FileNotFoundError:
        logger.warning(f"Airports CSV not found at {csv_path}, using empty dict")
    except Exception as e:
        logger.error(f"Error loading airports: {e}")
        raise
    
    return airports


def load_aircraft_types(csv_path: str) -> Dict[str, AircraftType]:
    """
    Parse aircraft_types.csv and produce AircraftType instances.
    
    Args:
        csv_path: Path to aircraft types CSV file
        
    Returns:
        Dictionary mapping type code to AircraftType instance
    """
    aircraft_types = {}
    
    try:
        # Resolve path (handle both with and without HackitAll2025-main prefix)
        resolved_path = _resolve_csv_path(csv_path)
        # CSV uses semicolon separator
        df = pd.read_csv(resolved_path, sep=';')
        logger.info(f"Loaded aircraft types CSV with {len(df)} rows")
        
        required_cols = ["type_code"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        for _, row in df.iterrows():
            type_code = str(row["type_code"])
            
            # Parse per-class capacities
            # CSV uses: first_class_seats, business_seats, premium_economy_seats, economy_seats
            # and: first_class_kits_capacity, business_kits_capacity, premium_economy_kits_capacity, economy_kits_capacity
            passenger_capacity = {}
            kit_capacity = {}
            
            # Map class types to CSV column names
            class_col_map = {
                "FIRST": ("first_class_seats", "first_class_kits_capacity"),
                "BUSINESS": ("business_seats", "business_kits_capacity"),
                "PREMIUM_ECONOMY": ("premium_economy_seats", "premium_economy_kits_capacity"),
                "ECONOMY": ("economy_seats", "economy_kits_capacity"),
            }
            
            for class_type in CLASS_TYPES:
                pass_col, kit_col = class_col_map[class_type]
                passenger_capacity[class_type] = int(row.get(pass_col, 0))
                kit_capacity[class_type] = int(row.get(kit_col, 0))
            
            # CSV uses cost_per_kg_per_km, not fuel_cost_per_km
            fuel_cost = float(row.get("cost_per_kg_per_km", 0.5))
            
            aircraft_type = AircraftType(
                type_code=type_code,
                passenger_capacity=passenger_capacity,
                kit_capacity=kit_capacity,
                fuel_cost_per_km=fuel_cost,
            )
            aircraft_types[type_code] = aircraft_type
            
            logger.debug(f"Loaded aircraft type {type_code}: {passenger_capacity}, {kit_capacity}")
            
    except FileNotFoundError:
        logger.warning(f"Aircraft types CSV not found at {csv_path}, using empty dict")
    except Exception as e:
        logger.error(f"Error loading aircraft types: {e}")
        raise
    
    logger.info(f"Successfully loaded {len(aircraft_types)} aircraft types")
    return aircraft_types


def load_flight_schedule(csv_path: str) -> Dict[str, Dict]:
    """
    Parse flight_plan.csv into flight templates.
    
    Args:
        csv_path: Path to flight plan CSV file
        
    Returns:
        Dictionary mapping flight_id to flight template dict
    """
    flight_templates = {}
    
    try:
        # Resolve path (handle both with and without HackitAll2025-main prefix)
        resolved_path = _resolve_csv_path(csv_path)
        df = pd.read_csv(resolved_path)
        logger.info(f"Loaded flight plan CSV with {len(df)} rows")
        
        required_cols = ["flight_id", "flight_number", "origin", "destination"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        for _, row in df.iterrows():
            flight_id = str(row["flight_id"])
            
            # Parse passenger counts per class
            planned_passengers = {}
            for class_type in CLASS_TYPES:
                pass_col = f"planned_passengers_{class_type}"
                planned_passengers[class_type] = int(row.get(pass_col, 0))
            
            template = {
                "flight_id": flight_id,
                "flight_number": str(row.get("flight_number", flight_id)),
                "origin": str(row["origin"]),
                "destination": str(row["destination"]),
                "scheduled_departure_day": int(row.get("scheduled_departure_day", 0)),
                "scheduled_departure_hour": int(row.get("scheduled_departure_hour", 0)),
                "scheduled_arrival_day": int(row.get("scheduled_arrival_day", 0)),
                "scheduled_arrival_hour": int(row.get("scheduled_arrival_hour", 0)),
                "planned_passengers": planned_passengers,
                "planned_distance": float(row.get("planned_distance", 0.0)),
                "aircraft_type": str(row.get("aircraft_type", "UNKNOWN")),
            }
            
            flight_templates[flight_id] = template
            
    except FileNotFoundError:
        logger.warning(f"Flight plan CSV not found at {csv_path}, using empty dict")
    except Exception as e:
        logger.error(f"Error loading flight schedule: {e}")
        raise
    
    return flight_templates

