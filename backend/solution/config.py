"""Configuration for solution-specific parameters."""

from dataclasses import dataclass
from typing import Dict


@dataclass
class SolutionConfig:
    """Configuration for solution strategies and optimization."""
    
    # === OPTIMIZED: PASSENGER LOADING PARAMETERS ===
    
    # Dynamic buffer based on stock health
    PASSENGER_BUFFER_PERCENT: float = 0.10  # 10% base (optimized from 15%)
    MIN_BUFFER_KITS: int = 2
    MAX_BUFFER_KITS: int = 8  # Reduced from 10 to save costs
    
    # Dynamic buffer thresholds
    HIGH_STOCK_BUFFER: float = 0.08   # 8% when stock > 50%
    MEDIUM_STOCK_BUFFER: float = 0.12  # 12% when stock 30-50%
    LOW_STOCK_BUFFER: float = 0.15    # 15% when stock < 30%
    
    # === OPTIMIZED: HUB REORDERING ===
    
    # Lower thresholds to reduce inventory costs
    HUB_REORDER_THRESHOLD: float = 0.25  # 25% (optimized from 30%)
    HUB_TARGET_LEVEL: float = 0.70  # 70% (optimized from 80%)
    
    # Demand-based ordering
    USE_DEMAND_BASED_ORDERING: bool = True
    DEMAND_SAFETY_MARGIN: float = 0.10  # 10% safety margin
    
    # === OUTSTATION MONITORING ===
    
    OUTSTATION_MIN_STOCK_THRESHOLD: float = 0.15  # 15% of capacity
    
    # === PLANNING HORIZON ===
    
    LOOKAHEAD_HOURS: int = 24
    DEMAND_HISTORY_HOURS: int = 48
    
    # === SPECIAL OPTIMIZATIONS ===
    
    # HUB gets minimal buffer (easy to restock)
    HUB_SPECIAL_BUFFER: float = 0.08  # 8% only
    
    # Short flights get less buffer (less risk)
    SHORT_FLIGHT_KM: int = 500
    SHORT_FLIGHT_BUFFER: float = 0.08
    
    # === COST OPTIMIZATION ===
    
    PURCHASE_COST_WEIGHT: float = 1.2
    PENALTY_COST_WEIGHT: float = 5.0  # High priority
    LOADING_COST_WEIGHT: float = 0.8
    
    # === STRATEGY SELECTION ===
    
    AGGRESSIVE_MODE: bool = False
    CONSERVATIVE_MODE: bool = False
    
    # === BATCH AND TIMING ===
    
    MIN_PURCHASE_QUANTITY: int = 5
    MAX_PURCHASE_QUANTITY: int = 100
    
    # Purchase in batches of this size
    PURCHASE_BATCH_SIZE: int = 10
    
    # === HUB MANAGEMENT ===
    
    # Hub codes (if applicable)
    HUB_AIRPORTS: list = None
    
    # Enable hub-based distribution strategy
    USE_HUB_STRATEGY: bool = False
    
    # === ADVANCED FEATURES ===
    
    # Enable machine learning predictions (if implemented)
    USE_ML_PREDICTIONS: bool = False
    
    # Enable dynamic adjustment based on performance
    ADAPTIVE_LEARNING: bool = False
    
    def __post_init__(self):
        """Initialize derived values."""
        if self.HUB_AIRPORTS is None:
            self.HUB_AIRPORTS = []
    
    @classmethod
    def default(cls) -> "SolutionConfig":
        """Create default configuration."""
        return cls()
    
    @classmethod
    def conservative(cls) -> "SolutionConfig":
        """Create conservative configuration (minimize risks)."""
        return cls(
            SAFETY_BUFFER=10,
            REORDER_THRESHOLD=0.5,
            TARGET_STOCK_LEVEL=75,
            DEMAND_MULTIPLIER=1.5,
            PENALTY_COST_WEIGHT=5.0,
            CONSERVATIVE_MODE=True,
        )
    
    @classmethod
    def aggressive(cls) -> "SolutionConfig":
        """Create aggressive configuration (minimize costs)."""
        return cls(
            SAFETY_BUFFER=2,
            REORDER_THRESHOLD=0.2,
            TARGET_STOCK_LEVEL=30,
            DEMAND_MULTIPLIER=1.0,
            PURCHASE_COST_WEIGHT=2.0,
            AGGRESSIVE_MODE=True,
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "SAFETY_BUFFER": self.SAFETY_BUFFER,
            "REORDER_THRESHOLD": self.REORDER_THRESHOLD,
            "TARGET_STOCK_LEVEL": self.TARGET_STOCK_LEVEL,
            "LOOKAHEAD_HOURS": self.LOOKAHEAD_HOURS,
            "DEMAND_MULTIPLIER": self.DEMAND_MULTIPLIER,
            "PURCHASE_COST_WEIGHT": self.PURCHASE_COST_WEIGHT,
            "PENALTY_COST_WEIGHT": self.PENALTY_COST_WEIGHT,
            "LOADING_COST_WEIGHT": self.LOADING_COST_WEIGHT,
            "AGGRESSIVE_MODE": self.AGGRESSIVE_MODE,
            "CONSERVATIVE_MODE": self.CONSERVATIVE_MODE,
        }
