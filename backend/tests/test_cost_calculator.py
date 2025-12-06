"""Tests for cost calculator module."""

import pytest
from backend.cost_calculator import (
    calculate_loading_cost,
    calculate_purchase_cost,
    calculate_understock_penalty,
    calculate_overstock_penalty,
)
from backend.models.flight import Flight, ReferenceHour
from backend.models.airport import Airport
from backend.config import KIT_DEFINITIONS, PENALTY_FACTORS


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
        planned_passengers={"FIRST": 10, "BUSINESS": 20},
        planned_distance=4000.0,
        aircraft_type="A320",
        event_type="SCHEDULED",
    )


@pytest.fixture
def sample_airport():
    """Create sample airport for testing."""
    return Airport(
        code="JFK",
        name="John F. Kennedy",
        is_hub=True,
        storage_capacity={"FIRST": 100, "BUSINESS": 200},
        loading_costs={"FIRST": 10.0, "BUSINESS": 8.0},
        processing_costs={"FIRST": 5.0, "BUSINESS": 4.0},
        processing_times={"FIRST": 2, "BUSINESS": 2},
    )


def test_calculate_loading_cost(sample_flight, sample_airport):
    """Test loading cost calculation."""
    kits = {"FIRST": 10, "BUSINESS": 20}
    cost = calculate_loading_cost(sample_flight, kits, sample_airport)
    
    expected = 10 * 10.0 + 20 * 8.0  # 10 FIRST @ 10.0, 20 BUSINESS @ 8.0
    assert cost == expected


def test_calculate_purchase_cost():
    """Test purchase cost calculation."""
    kits = {"FIRST": 10, "BUSINESS": 20}
    cost = calculate_purchase_cost(kits, KIT_DEFINITIONS)
    
    expected = 10 * 50.0 + 20 * 30.0  # 10 FIRST @ 50.0, 20 BUSINESS @ 30.0
    assert cost == expected


def test_calculate_understock_penalty(sample_airport):
    """Test understock penalty calculation."""
    inventory = {"FIRST": -10, "BUSINESS": 5}
    penalty = calculate_understock_penalty(sample_airport, inventory)
    
    expected = 10 * PENALTY_FACTORS["NEGATIVE_INVENTORY"]
    assert penalty == expected


def test_calculate_overstock_penalty(sample_airport):
    """Test overstock penalty calculation."""
    inventory = {"FIRST": 150, "BUSINESS": 200}  # FIRST exceeds capacity of 100
    penalty = calculate_overstock_penalty(sample_airport, inventory)
    
    expected = 50 * PENALTY_FACTORS["OVER_CAPACITY"]  # 150 - 100 = 50 excess
    assert penalty == expected

