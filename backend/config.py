"""Configuration module for constants, penalty factors, and settings."""

from typing import Dict
from pydantic_settings import BaseSettings


# Game constants
TOTAL_ROUNDS = 720
MIN_START_HOUR = 4
CLASS_TYPES = ["FIRST", "BUSINESS", "PREMIUM_ECONOMY", "ECONOMY"]


# Penalty factors (exact names as per repository)
NEGATIVE_INVENTORY_FACTOR = 1000.0
OVER_CAPACITY_FACTOR = 500.0
FLIGHT_OVERLOAD_FACTOR = 2000.0
UNFULFILLED_PASSENGERS_FACTOR = 300.0
INCORRECT_FLIGHT_LOAD_FACTOR = 500.0
END_OF_GAME_NEGATIVE_INVENTORY_FACTOR = 2000.0
END_OF_GAME_OVER_CAPACITY_FACTOR = 1000.0


# Penalty factors dictionary for easy access
PENALTY_FACTORS = {
    "NEGATIVE_INVENTORY": NEGATIVE_INVENTORY_FACTOR,
    "OVER_CAPACITY": OVER_CAPACITY_FACTOR,
    "FLIGHT_OVERLOAD": FLIGHT_OVERLOAD_FACTOR,
    "UNFULFILLED_PASSENGERS": UNFULFILLED_PASSENGERS_FACTOR,
    "INCORRECT_FLIGHT_LOAD": INCORRECT_FLIGHT_LOAD_FACTOR,
    "END_OF_GAME_NEGATIVE_INVENTORY": END_OF_GAME_NEGATIVE_INVENTORY_FACTOR,
    "END_OF_GAME_OVER_CAPACITY": END_OF_GAME_OVER_CAPACITY_FACTOR,
}


# Kit definitions: cost, weight (kg), lead_time (hours)
KIT_DEFINITIONS: Dict[str, Dict[str, float]] = {
    "FIRST": {
        "cost": 50.0,
        "weight": 2.5,
        "lead_time": 24,
    },
    "BUSINESS": {
        "cost": 30.0,
        "weight": 1.5,
        "lead_time": 24,
    },
    "PREMIUM_ECONOMY": {
        "cost": 15.0,
        "weight": 1.0,
        "lead_time": 24,
    },
    "ECONOMY": {
        "cost": 10.0,
        "weight": 0.8,
        "lead_time": 24,
    },
}


# File path constants (relative to backend directory)
# Data files are in ../HackitAll2025-main/eval-platform/...
CSV_BASE_PATH = "../HackitAll2025-main/eval-platform/src/main/resources/liquibase/data"
AIRPORTS_CSV = f"{CSV_BASE_PATH}/airports_with_stocks.csv"
AIRCRAFT_TYPES_CSV = f"{CSV_BASE_PATH}/aircraft_types.csv"
FLIGHT_PLAN_CSV = f"{CSV_BASE_PATH}/flight_plan.csv"


# External API configuration
class Config(BaseSettings):
    """Application configuration with environment variable support."""
    
    # API Configuration
    API_BASE_URL: str = "http://localhost:8080"
    API_KEY_HEADER: str = "API-KEY"
    
    # API Endpoints
    ENDPOINT_START_SESSION: str = "/api/v1/session/start"
    ENDPOINT_PLAY_ROUND: str = "/api/v1/play/round"
    ENDPOINT_STOP_SESSION: str = "/api/v1/session/end"
    
    # Optimizer parameters
    SAFETY_BUFFER: int = 0
    REORDER_THRESHOLD: int = 10
    TARGET_STOCK_LEVEL: int = 50
    LOOKAHEAD_HOURS: int = 24
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "simulation.log"
    
    # Conservative defaults for missing CSV data
    DEFAULT_PROCESSING_TIME: int = 2  # hours
    DEFAULT_LOADING_COST: float = 10.0
    DEFAULT_PROCESSING_COST: float = 5.0
    DEFAULT_STORAGE_CAPACITY: int = 100
    DEFAULT_HUB_INVENTORY: int = 50
    DEFAULT_OUTSTATION_INVENTORY: int = 20
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


# API endpoints dictionary
ENDPOINTS = {
    "start": "/api/v1/session/start",
    "play": "/api/v1/play/round",
    "stop": "/api/v1/session/end",
}

