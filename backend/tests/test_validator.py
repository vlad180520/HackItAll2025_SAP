"""Tests for validator module."""

import pytest
from backend.validator import Validator, ValidationReport
from backend.models.kit import KitLoadDecision
from backend.models.game_state import GameState
from backend.models.flight import Flight, ReferenceHour
from backend.models.airport import Airport
from backend.models.aircraft import AircraftType
from backend.config import KIT_DEFINITIONS


@pytest.fixture
def sample_airports():
    """Create sample airports for testing."""
    return {
        "JFK": Airport(
            code="JFK",
            name="John F. Kennedy",
            is_hub=True,
            storage_capacity={"FIRST": 100, "BUSINESS": 200},
            loading_costs={"FIRST": 10.0, "BUSINESS": 8.0},
            processing_costs={"FIRST": 5.0, "BUSINESS": 4.0},
            processing_times={"FIRST": 2, "BUSINESS": 2},
            current_inventory={"FIRST": 50, "BUSINESS": 50},
        )
    }


@pytest.fixture
def sample_aircraft():
    """Create sample aircraft for testing."""
    return {
        "A320": AircraftType(
            type_code="A320",
            passenger_capacity={"FIRST": 0, "BUSINESS": 20},
            kit_capacity={"FIRST": 0, "BUSINESS": 20},
            fuel_cost_per_km=0.5,
        )
    }


@pytest.fixture
def sample_state():
    """Create sample game state for testing."""
    return GameState(
        current_day=0,
        current_hour=6,
        airport_inventories={
            "JFK": {"FIRST": 50, "BUSINESS": 50},
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
        planned_passengers={"FIRST": 0, "BUSINESS": 20},
        planned_distance=4000.0,
        aircraft_type="A320",
        event_type="SCHEDULED",
    )


def test_validator_initialization(sample_airports, sample_aircraft):
    """Test validator initialization."""
    validator = Validator(sample_airports, sample_aircraft, KIT_DEFINITIONS)
    assert validator.airports == sample_airports
    assert validator.aircraft == sample_aircraft


def test_validate_decisions_valid(sample_airports, sample_aircraft, sample_state, sample_flight):
    """Test validation of valid decisions."""
    validator = Validator(sample_airports, sample_aircraft, KIT_DEFINITIONS)
    
    decision = KitLoadDecision(
        flight_id="FL001",
        kits_per_class={"FIRST": 0, "BUSINESS": 20},
    )
    
    report = validator.validate_decisions([decision], [], sample_state, [sample_flight])
    
    assert report.is_valid()
    assert len(report.errors) == 0


def test_validate_decisions_capacity_exceeded(sample_airports, sample_aircraft, sample_state, sample_flight):
    """Test validation detects capacity exceeded."""
    validator = Validator(sample_airports, sample_aircraft, KIT_DEFINITIONS)
    
    decision = KitLoadDecision(
        flight_id="FL001",
        kits_per_class={"FIRST": 0, "BUSINESS": 25},  # Exceeds capacity of 20
    )
    
    report = validator.validate_decisions([decision], [], sample_state, [sample_flight])
    
    assert not report.is_valid()
    assert len(report.errors) > 0
    assert any("capacity exceeded" in error.lower() for error in report.errors)


def test_validate_decisions_invalid_flight(sample_airports, sample_aircraft, sample_state):
    """Test validation detects invalid flight ID."""
    validator = Validator(sample_airports, sample_aircraft, KIT_DEFINITIONS)
    
    decision = KitLoadDecision(
        flight_id="INVALID",
        kits_per_class={"FIRST": 0, "BUSINESS": 20},
    )
    
    report = validator.validate_decisions([decision], [], sample_state, [])
    
    assert not report.is_valid()
    assert len(report.errors) > 0
    assert any("does not exist" in error.lower() for error in report.errors)

