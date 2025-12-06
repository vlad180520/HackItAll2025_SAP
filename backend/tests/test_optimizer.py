"""Tests for optimizer module."""

import pytest
from backend.optimizer import GreedyOptimizer
from backend.models.game_state import GameState
from backend.models.flight import Flight, ReferenceHour
from backend.models.airport import Airport
from backend.models.aircraft import AircraftType
from backend.config import Config


@pytest.fixture
def sample_state():
    """Create sample game state for testing."""
    return GameState(
        current_day=0,
        current_hour=6,
        airport_inventories={
            "JFK": {"FIRST": 50, "BUSINESS": 50, "PREMIUM_ECONOMY": 50, "ECONOMY": 100},
        },
        in_process_kits={},
        pending_movements=[],
        total_cost=0.0,
        penalty_log=[],
        flight_history=[],
    )


@pytest.fixture
def sample_airports():
    """Create sample airports for testing."""
    return {
        "JFK": Airport(
            code="JFK",
            name="John F. Kennedy",
            is_hub=True,
            storage_capacity={"FIRST": 100, "BUSINESS": 200, "PREMIUM_ECONOMY": 300, "ECONOMY": 500},
            loading_costs={"FIRST": 10.0, "BUSINESS": 8.0, "PREMIUM_ECONOMY": 6.0, "ECONOMY": 5.0},
            processing_costs={"FIRST": 5.0, "BUSINESS": 4.0, "PREMIUM_ECONOMY": 3.0, "ECONOMY": 2.0},
            processing_times={"FIRST": 2, "BUSINESS": 2, "PREMIUM_ECONOMY": 2, "ECONOMY": 2},
        )
    }


@pytest.fixture
def sample_aircraft():
    """Create sample aircraft for testing."""
    return {
        "A320": AircraftType(
            type_code="A320",
            passenger_capacity={"FIRST": 0, "BUSINESS": 20, "PREMIUM_ECONOMY": 30, "ECONOMY": 120},
            kit_capacity={"FIRST": 0, "BUSINESS": 20, "PREMIUM_ECONOMY": 30, "ECONOMY": 120},
            fuel_cost_per_km=0.5,
        )
    }


@pytest.fixture
def sample_flight():
    """Create sample flight for testing."""
    return Flight(
        flight_id="FL001",
        flight_number="AA100",
        origin="JFK",
        destination="LAX",
        scheduled_departure=ReferenceHour(day=0, hour=6),
        scheduled_arrival=ReferenceHour(day=0, hour=12),
        planned_passengers={"FIRST": 0, "BUSINESS": 20, "PREMIUM_ECONOMY": 30, "ECONOMY": 100},
        planned_distance=4000.0,
        aircraft_type="A320",
        event_type="SCHEDULED",
    )


def test_optimizer_initialization():
    """Test optimizer initialization."""
    config = Config()
    optimizer = GreedyOptimizer(config)
    assert optimizer.safety_buffer == config.SAFETY_BUFFER
    assert optimizer.reorder_threshold == config.REORDER_THRESHOLD


def test_optimizer_decide(sample_state, sample_airports, sample_aircraft, sample_flight):
    """Test optimizer produces decisions."""
    config = Config()
    optimizer = GreedyOptimizer(config)
    
    decisions, purchases, rationale = optimizer.decide(
        sample_state, [sample_flight], sample_airports, sample_aircraft
    )
    
    assert len(decisions) > 0
    assert isinstance(rationale, str)
    
    # Check decision structure
    decision = decisions[0]
    assert decision.flight_id == "FL001"
    assert "BUSINESS" in decision.kits_per_class
    assert decision.kits_per_class["BUSINESS"] <= 20  # Should not exceed capacity

