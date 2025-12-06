"""Data loader module for parsing CSV files."""

import logging
import pandas as pd
from typing import Dict
from pathlib import Path

from .models.airport import Airport
from .models.aircraft import AircraftType
from .config import Config, CLASS_TYPES

logger = logging.getLogger(__name__)


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
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded airports CSV with {len(df)} rows")
        
        # Expected columns (with conservative defaults if missing)
        required_cols = ["code", "name", "is_hub"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        for _, row in df.iterrows():
            code = str(row["code"])
            name = str(row.get("name", code))
            is_hub = bool(row.get("is_hub", False))
            
            # Parse per-class data with defaults
            storage_capacity = {}
            loading_costs = {}
            processing_costs = {}
            processing_times = {}
            current_inventory = {}
            
            for class_type in CLASS_TYPES:
                # Storage capacity
                cap_col = f"storage_capacity_{class_type}"
                storage_capacity[class_type] = int(row.get(cap_col, config.DEFAULT_STORAGE_CAPACITY))
                
                # Loading costs
                load_col = f"loading_cost_{class_type}"
                loading_costs[class_type] = float(row.get(load_col, config.DEFAULT_LOADING_COST))
                
                # Processing costs
                proc_cost_col = f"processing_cost_{class_type}"
                processing_costs[class_type] = float(row.get(proc_cost_col, config.DEFAULT_PROCESSING_COST))
                
                # Processing times
                proc_time_col = f"processing_time_{class_type}"
                processing_times[class_type] = int(row.get(proc_time_col, config.DEFAULT_PROCESSING_TIME))
                
                # Initial inventory
                inv_col = f"initial_inventory_{class_type}"
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
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded aircraft types CSV with {len(df)} rows")
        
        required_cols = ["type_code"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        for _, row in df.iterrows():
            type_code = str(row["type_code"])
            
            # Parse per-class capacities
            passenger_capacity = {}
            kit_capacity = {}
            
            for class_type in CLASS_TYPES:
                pass_col = f"passenger_capacity_{class_type}"
                kit_col = f"kit_capacity_{class_type}"
                
                passenger_capacity[class_type] = int(row.get(pass_col, 0))
                kit_capacity[class_type] = int(row.get(kit_col, 0))
            
            fuel_cost = float(row.get("fuel_cost_per_km", 0.5))
            
            aircraft_type = AircraftType(
                type_code=type_code,
                passenger_capacity=passenger_capacity,
                kit_capacity=kit_capacity,
                fuel_cost_per_km=fuel_cost,
            )
            aircraft_types[type_code] = aircraft_type
            
    except FileNotFoundError:
        logger.warning(f"Aircraft types CSV not found at {csv_path}, using empty dict")
    except Exception as e:
        logger.error(f"Error loading aircraft types: {e}")
        raise
    
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
        df = pd.read_csv(csv_path)
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

