"""Tests for data loader module."""

import pytest
import pandas as pd
from pathlib import Path
from backend.data_loader import load_airports, load_aircraft_types, load_flight_schedule
from backend.config import Config


def test_load_airports_empty_file(tmp_path):
    """Test loading airports with empty CSV."""
    csv_path = tmp_path / "airports.csv"
    csv_path.write_text("code,name,is_hub\n")
    
    config = Config()
    airports = load_airports(str(csv_path), config)
    
    assert isinstance(airports, dict)
    assert len(airports) == 0


def test_load_airports_with_data(tmp_path):
    """Test loading airports with sample data."""
    csv_path = tmp_path / "airports.csv"
    csv_path.write_text(
        "code,name,is_hub,storage_capacity_FIRST,storage_capacity_BUSINESS,"
        "loading_cost_FIRST,loading_cost_BUSINESS,"
        "processing_cost_FIRST,processing_cost_BUSINESS,"
        "processing_time_FIRST,processing_time_BUSINESS,"
        "initial_inventory_FIRST,initial_inventory_BUSINESS\n"
        "JFK,John F. Kennedy,True,100,200,10.0,8.0,5.0,4.0,2,2,50,50\n"
    )
    
    config = Config()
    airports = load_airports(str(csv_path), config)
    
    assert len(airports) == 1
    assert "JFK" in airports
    assert airports["JFK"].code == "JFK"
    assert airports["JFK"].is_hub is True


def test_load_aircraft_types_empty_file(tmp_path):
    """Test loading aircraft types with empty CSV."""
    csv_path = tmp_path / "aircraft.csv"
    csv_path.write_text("type_code\n")
    
    aircraft = load_aircraft_types(str(csv_path))
    
    assert isinstance(aircraft, dict)
    assert len(aircraft) == 0


def test_load_aircraft_types_with_data(tmp_path):
    """Test loading aircraft types with sample data."""
    csv_path = tmp_path / "aircraft.csv"
    csv_path.write_text(
        "type_code,passenger_capacity_FIRST,passenger_capacity_BUSINESS,"
        "kit_capacity_FIRST,kit_capacity_BUSINESS,fuel_cost_per_km\n"
        "A320,0,20,0,20,0.5\n"
    )
    
    aircraft = load_aircraft_types(str(csv_path))
    
    assert len(aircraft) == 1
    assert "A320" in aircraft
    assert aircraft["A320"].type_code == "A320"
    assert aircraft["A320"].fuel_cost_per_km == 0.5


def test_load_flight_schedule_empty_file(tmp_path):
    """Test loading flight schedule with empty CSV."""
    csv_path = tmp_path / "flights.csv"
    csv_path.write_text("flight_id,flight_number,origin,destination\n")
    
    flights = load_flight_schedule(str(csv_path))
    
    assert isinstance(flights, dict)
    assert len(flights) == 0


def test_load_flight_schedule_with_data(tmp_path):
    """Test loading flight schedule with sample data."""
    csv_path = tmp_path / "flights.csv"
    csv_path.write_text(
        "flight_id,flight_number,origin,destination,"
        "scheduled_departure_day,scheduled_departure_hour,"
        "scheduled_arrival_day,scheduled_arrival_hour,"
        "planned_passengers_FIRST,planned_passengers_BUSINESS,"
        "planned_distance,aircraft_type\n"
        "FL001,AA100,JFK,LAX,0,6,0,12,10,20,4000.0,A320\n"
    )
    
    flights = load_flight_schedule(str(csv_path))
    
    assert len(flights) == 1
    assert "FL001" in flights
    assert flights["FL001"]["origin"] == "JFK"
    assert flights["FL001"]["destination"] == "LAX"

