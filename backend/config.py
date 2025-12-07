"""Configuration module for constants, penalty factors, and settings."""

from typing import Dict
from pydantic_settings import BaseSettings


# Game constants
TOTAL_ROUNDS = 720
MIN_START_HOUR = 4
CLASS_TYPES = ["FIRST", "BUSINESS", "PREMIUM_ECONOMY", "ECONOMY"]


# Penalty factors - MUST MATCH PenaltyFactors.java exactly!
# Source: eval-platform/.../service/impl/PenaltyFactors.java
FLIGHT_OVERLOAD_FACTOR_PER_DISTANCE = 5.0
UNFULFILLED_KIT_FACTOR_PER_DISTANCE = 0.003
INCORRECT_FLIGHT_LOAD = 5000.0
NEGATIVE_INVENTORY_FACTOR = 5342.0  # Very high - avoid negative stock!
OVER_CAPACITY_FACTOR = 777.0
END_OF_GAME_REMAINING_STOCK = 0.0013
EARLY_END_OF_GAME = 1000.0
END_OF_GAME_PENDING_KIT_PROCESSING = 0.0013
END_OF_GAME_UNFULFILLED_FLIGHT_KITS = 1.5


# Penalty factors dictionary for easy access
PENALTY_FACTORS = {
    "NEGATIVE_INVENTORY": NEGATIVE_INVENTORY_FACTOR,
    "OVER_CAPACITY": OVER_CAPACITY_FACTOR,
    "FLIGHT_OVERLOAD": FLIGHT_OVERLOAD_FACTOR_PER_DISTANCE,  # Per distance
    "UNFULFILLED_PASSENGERS": UNFULFILLED_KIT_FACTOR_PER_DISTANCE,  # Per distance
    "INCORRECT_FLIGHT_LOAD": INCORRECT_FLIGHT_LOAD,
    "END_OF_GAME_REMAINING_STOCK": END_OF_GAME_REMAINING_STOCK,
    "EARLY_END_OF_GAME": EARLY_END_OF_GAME,
    "END_OF_GAME_PENDING_KIT_PROCESSING": END_OF_GAME_PENDING_KIT_PROCESSING,
    "END_OF_GAME_UNFULFILLED_FLIGHT_KITS": END_OF_GAME_UNFULFILLED_FLIGHT_KITS,
}


# Kit definitions - MUST MATCH KitType.java exactly!
# Source: eval-platform/.../model/KitType.java
# Format: (weight_kg, kit_cost, replacement_lead_time_hours)
# A_FIRST_CLASS(5d, 200d, 48), B_BUSINESS(3d, 150d, 36),
# C_PREMIUM_ECONOMY(2.5d, 100d, 24), D_ECONOMY(1.5d, 50d, 12)
KIT_DEFINITIONS: Dict[str, Dict[str, float]] = {
    "FIRST": {
        "cost": 200.0,
        "weight": 5.0,
        "lead_time": 48,  # 48 hours for replacement at HUB
    },
    "BUSINESS": {
        "cost": 150.0,
        "weight": 3.0,
        "lead_time": 36,  # 36 hours for replacement at HUB
    },
    "PREMIUM_ECONOMY": {
        "cost": 100.0,
        "weight": 2.5,
        "lead_time": 24,  # 24 hours for replacement at HUB
    },
    "ECONOMY": {
        "cost": 50.0,
        "weight": 1.5,
        "lead_time": 12,  # 12 hours for replacement at HUB
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

