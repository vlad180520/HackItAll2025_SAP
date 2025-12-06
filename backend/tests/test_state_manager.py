"""Tests for state manager module."""

import pytest
from backend.state_manager import StateManager
from backend.models.game_state import GameState, KitMovement
from backend.models.flight import Flight, ReferenceHour
from backend.models.kit import KitLoadDecision
from backend.models.airport import Airport


@pytest.fixture
def initial_state():
    """Create initial game state for testing."""
    return GameState(
        current_day=0,
        current_hour=4,
        airport_inventories={
            "JFK": {"FIRST": 50, "BUSINESS": 50, "PREMIUM_ECONOMY": 50, "ECONOMY": 50},
            "LAX": {"FIRST": 20, "BUSINESS": 20, "PREMIUM_ECONOMY": 20, "ECONOMY": 20},
        },
        in_process_kits={},
        pending_movements=[],
        total_cost=0.0,
        penalty_log=[],
        flight_history=[],
    )


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
        planned_passengers={"FIRST": 10, "BUSINESS": 20, "PREMIUM_ECONOMY": 30, "ECONOMY": 100},
        planned_distance=4000.0,
        aircraft_type="A320",
        event_type="SCHEDULED",
    )


def test_state_manager_initialization(initial_state):
    """Test state manager initialization."""
    manager = StateManager(initial_state)
    assert manager.state.current_day == 0
    assert manager.state.current_hour == 4


def test_apply_kit_loads(initial_state, sample_flight):
    """Test applying kit load decisions."""
    manager = StateManager(initial_state)
    
    decision = KitLoadDecision(
        flight_id="FL001",
        kits_per_class={"FIRST": 10, "BUSINESS": 20, "PREMIUM_ECONOMY": 30, "ECONOMY": 100},
    )
    
    manager.apply_kit_loads([decision], [sample_flight])
    
    # Check inventory decremented at origin
    assert manager.get_inventory("JFK", "FIRST") == 40
    assert manager.get_inventory("JFK", "BUSINESS") == 30
    
    # Check pending movement created
    assert len(manager.state.pending_movements) == 1
    assert manager.state.pending_movements[0].airport == "LAX"


def test_advance_time_to(initial_state):
    """Test advancing time."""
    manager = StateManager(initial_state)
    
    # Add a pending movement
    movement = KitMovement(
        movement_type="LOAD",
        airport="LAX",
        kits_per_class={"FIRST": 10},
        execute_time=ReferenceHour(day=0, hour=12),
    )
    manager.state.pending_movements.append(movement)
    
    # Advance to hour 12
    airports = {
        "LAX": Airport(
            code="LAX",
            name="Los Angeles",
            is_hub=False,
            storage_capacity={"FIRST": 100},
            loading_costs={"FIRST": 10.0},
            processing_costs={"FIRST": 5.0},
            processing_times={"FIRST": 2},
        )
    }
    
    manager.advance_time_to(0, 12, airports)
    
    assert manager.state.current_day == 0
    assert manager.state.current_hour == 12


def test_check_negative_inventories(initial_state):
    """Test checking for negative inventories."""
    manager = StateManager(initial_state)
    
    # Set negative inventory
    manager.state.airport_inventories["JFK"]["FIRST"] = -10
    
    negatives = manager.check_negative_inventories()
    
    assert len(negatives) == 1
    assert negatives[0] == ("JFK", "FIRST", -10)

