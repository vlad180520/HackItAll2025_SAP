"""
Test that DecisionMaker uses FinalStrategy and returns valid decisions.
"""
import sys
sys.path.insert(0, '.')

from solution.decision_maker import DecisionMaker
from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.airport import Airport
from models.aircraft import AircraftType

def test_decision_maker():
    """Test that DecisionMaker makes valid decisions."""
    
    print("Creating DecisionMaker...")
    dm = DecisionMaker()
    
    # Verify strategy type
    strategy_name = type(dm.strategy).__name__
    print(f"Strategy type: {strategy_name}")
    
    if strategy_name != "FinalStrategy":
        print(f"FAIL: Expected FinalStrategy, got {strategy_name}")
        return False
    
    # Create minimal test data
    state = GameState(
        current_day=0,
        current_hour=0,
        airport_inventories={},
        pending_movements=[],
        flight_history=[],
        total_cost=0.0,
        in_process_kits={},
        penalty_log=[],
    )
    
    airports = {
        "HUB1": Airport(
            code="HUB1",
            name="Hub",
            is_hub=True,
            processing_times={"FIRST": 6, "BUSINESS": 4, "PREMIUM_ECONOMY": 2, "ECONOMY": 1},
            processing_costs={"FIRST": 8, "BUSINESS": 6, "PREMIUM_ECONOMY": 2, "ECONOMY": 1},
            loading_costs={"FIRST": 1, "BUSINESS": 0.75, "PREMIUM_ECONOMY": 0.5, "ECONOMY": 0.5},
            current_inventory={"FIRST": 1659, "BUSINESS": 5184, "PREMIUM_ECONOMY": 2668, "ECONOMY": 23651},
            storage_capacity={"FIRST": 18109, "BUSINESS": 18109, "PREMIUM_ECONOMY": 9818, "ECONOMY": 95075},
        ),
        "OUT1": Airport(
            code="OUT1",
            name="Outstation",
            is_hub=False,
            processing_times={"FIRST": 45, "BUSINESS": 28, "PREMIUM_ECONOMY": 12, "ECONOMY": 4},
            processing_costs={"FIRST": 6.67, "BUSINESS": 5.23, "PREMIUM_ECONOMY": 3.55, "ECONOMY": 1.65},
            loading_costs={"FIRST": 3.3, "BUSINESS": 2.09, "PREMIUM_ECONOMY": 2.01, "ECONOMY": 1.38},
            current_inventory={"FIRST": 158, "BUSINESS": 105, "PREMIUM_ECONOMY": 135, "ECONOMY": 304},
            storage_capacity={"FIRST": 445, "BUSINESS": 445, "PREMIUM_ECONOMY": 290, "ECONOMY": 803},
        ),
    }
    
    aircraft = {
        "A320": AircraftType(
            type_code="A320",
            fuel_cost_per_km=0.5,
            kit_capacity={"FIRST": 10, "BUSINESS": 30, "PREMIUM_ECONOMY": 50, "ECONOMY": 150},
            passenger_capacity={"FIRST": 10, "BUSINESS": 30, "PREMIUM_ECONOMY": 50, "ECONOMY": 150},
        )
    }
    
    flights = [
        Flight(
            flight_id="test-1",
            flight_number="AB001",
            origin="HUB1",
            destination="OUT1",
            aircraft_type="A320",
            scheduled_departure=ReferenceHour(day=0, hour=0),
            scheduled_arrival=ReferenceHour(day=0, hour=2),
            planned_passengers={"FIRST": 5, "BUSINESS": 20, "PREMIUM_ECONOMY": 30, "ECONOMY": 100},
            actual_passengers={"FIRST": 5, "BUSINESS": 20, "PREMIUM_ECONOMY": 30, "ECONOMY": 100},
            planned_distance=1000.0,
            event_type="SCHEDULED",
        )
    ]
    
    # Test make_decisions
    print("Testing make_decisions()...")
    loads, purchases = dm.make_decisions(state, flights, airports, aircraft)
    
    print(f"Loads returned: {len(loads)}")
    print(f"Purchases returned: {len(purchases)}")
    
    if len(loads) == 0:
        print("FAIL: Expected at least 1 load decision")
        return False
    
    # Verify load decision
    load = loads[0]
    print(f"Load decision: {load.kits_per_class}")
    
    expected = {"FIRST": 5, "BUSINESS": 20, "PREMIUM_ECONOMY": 30, "ECONOMY": 100}
    for class_type, exp_qty in expected.items():
        actual = load.kits_per_class.get(class_type, 0)
        if actual != exp_qty:
            print(f"FAIL: {class_type} expected {exp_qty}, got {actual}")
            return False
    
    print("✓ DecisionMaker test PASSED!")
    return True

if __name__ == "__main__":
    success = test_decision_maker()
    sys.exit(0 if success else 1)
