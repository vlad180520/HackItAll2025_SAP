"""Configuration for solution-specific parameters."""

from dataclasses import dataclass
from typing import Dict


@dataclass
class SolutionConfig:
    """Configuration for solution strategies and optimization."""
    
    # === CRITICAL: PASSENGER LOADING PARAMETERS ===
    
    # Buffer for passenger loads: ALWAYS load more than passengers!
    PASSENGER_BUFFER_PERCENT: float = 0.15  # 15% extra
    MIN_BUFFER_KITS: int = 2  # Minimum 2 extra kits per class
    MAX_BUFFER_KITS: int = 10  # Max extra to avoid waste
    
    # === HUB REORDERING (ONLY AT HUB1) ===
    
    # Reorder at HUB1 when stock drops below this percentage
    HUB_REORDER_THRESHOLD: float = 0.30  # 30% of capacity
    
    # Target stock level at HUB1 after reordering
    HUB_TARGET_LEVEL: float = 0.80  # 80% of capacity
    
    # === OUTSTATION MONITORING ===
    
    # Alert threshold for outstations (no direct ordering)
    OUTSTATION_MIN_STOCK_THRESHOLD: float = 0.20  # 20% of capacity
    
    # === PLANNING HORIZON ===
    
    # Lookahead hours: how many hours ahead to consider for planning
    LOOKAHEAD_HOURS: int = 24
    
    # Historical demand tracking for pattern detection
    DEMAND_HISTORY_HOURS: int = 48
    
    # === LEGACY PARAMETERS (kept for compatibility) ===
    
    # Safety buffer: extra kits to keep above minimum requirements
    SAFETY_BUFFER: int = 5
    
    # Reorder threshold: when stock falls below this ratio, trigger purchase
    REORDER_THRESHOLD: float = 0.3  # 30% of target
    
    # Target stock level: aim to maintain this many kits per class
    TARGET_STOCK_LEVEL: int = 50
    
    # Demand multiplier: factor to apply to predicted demand for safety
    DEMAND_MULTIPLIER: float = 1.2  # 20% safety margin
    
    # === COST OPTIMIZATION ===
    
    # Purchase cost weight: importance of minimizing purchase costs
    PURCHASE_COST_WEIGHT: float = 1.0
    
    # Penalty cost weight: importance of avoiding penalties
    PENALTY_COST_WEIGHT: float = 3.0
    
    # Loading cost weight: importance of minimizing loading costs
    LOADING_COST_WEIGHT: float = 0.5
    
    # === STRATEGY SELECTION ===
    
    # Enable aggressive optimization (takes more risks)
    AGGRESSIVE_MODE: bool = False
    
    # Enable conservative mode (plays it safe)
    CONSERVATIVE_MODE: bool = False
    
    # === BATCH AND TIMING ===
    
    # Minimum purchase quantity per order
    MIN_PURCHASE_QUANTITY: int = 10
    
    # Maximum purchase quantity per order
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
