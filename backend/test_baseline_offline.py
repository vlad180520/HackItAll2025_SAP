"""
Offline test for BaselineStrategy - verify it returns NOTHING.
"""
import sys
sys.path.insert(0, '.')

from solution.strategies.baseline_strategy import BaselineStrategy
from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.airport import Airport
from models.aircraft import AircraftType

def test_baseline():
    """Test that baseline returns empty lists."""
    
    # Create strategy
    strategy = BaselineStrategy()
    
    # Create minimal test data with all required fields
    state = GameState(
        current_day=0,
        current_hour=0,
        airport_inventories={"HUB1": {"FIRST": 1000, "BUSINESS": 5000}},
        pending_movements=[],
        flight_history=[],
        total_cost=0.0,
        in_process_kits={},
        penalty_log=[],
    )
    
    # Create a test airport with correct field names
    airports = {
        "HUB1": Airport(
            code="HUB1",
            name="Hub",
            is_hub=True,
            processing_times={"FIRST": 6, "BUSINESS": 4},
            processing_costs={"FIRST": 8, "BUSINESS": 6},
            loading_costs={"FIRST": 1, "BUSINESS": 0.75},
            current_inventory={"FIRST": 1000, "BUSINESS": 5000},
            storage_capacity={"FIRST": 18000, "BUSINESS": 18000},
        )
    }
    
    # Create aircraft with correct field names
    aircraft = {
        "A320": AircraftType(
            type_code="A320",
            fuel_cost_per_km=0.5,
            kit_capacity={"FIRST": 10, "BUSINESS": 30},
            passenger_capacity={"FIRST": 10, "BUSINESS": 30},
        )
    }
    
    # Create test flights with ALL required fields
    flights = [
        Flight(
            flight_id="test-1",
            flight_number="AB001",
            origin="HUB1",
            destination="OUT1",
            aircraft_type="A320",
            scheduled_departure=ReferenceHour(day=0, hour=0),
            scheduled_arrival=ReferenceHour(day=0, hour=2),
            actual_departure=None,
            actual_arrival=None,
            planned_passengers={"FIRST": 5, "BUSINESS": 20},
            actual_passengers={"FIRST": 5, "BUSINESS": 20},
            planned_distance=1000.0,
            actual_distance=None,
            event_type="SCHEDULED",
        )
    ]
    
    # Run optimization for 100 rounds (simulating multiple days)
    print("Testing BaselineStrategy for 100 rounds...")
    
    total_loads = 0
    total_purchases = 0
    
    for round_num in range(100):
        loads, purchases = strategy.optimize(state, flights, airports, aircraft)
        
        total_loads += len(loads)
        total_purchases += len(purchases)
        
        # Verify EMPTY returns
        if len(loads) != 0:
            print(f"FAIL: Round {round_num}: Expected 0 loads, got {len(loads)}")
            return False
        if len(purchases) != 0:
            print(f"FAIL: Round {round_num}: Expected 0 purchases, got {len(purchases)}")
            return False
        
        # Advance time
        state.current_hour += 1
        if state.current_hour >= 24:
            state.current_hour = 0
            state.current_day += 1
    
    print(f"✓ All 100 rounds returned EMPTY (total loads: {total_loads}, purchases: {total_purchases})")
    print("✓ BaselineStrategy test PASSED!")
    return True

if __name__ == "__main__":
    success = test_baseline()
    sys.exit(0 if success else 1)
