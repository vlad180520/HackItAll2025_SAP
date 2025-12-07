"""
Test WorkingStrategy - verify it makes CORRECT decisions.
"""
import sys
sys.path.insert(0, '.')

from solution.strategies.working_strategy import WorkingStrategy
from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.airport import Airport
from models.aircraft import AircraftType

def test_working_strategy():
    """Test that working strategy makes correct decisions."""
    
    print("Creating WorkingStrategy...")
    strategy = WorkingStrategy()
    
    # Create test data matching real CSV structure
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
    
    # Create airports with realistic data
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
            name="Outstation 1",
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
    
    # Create test flights departing now
    flights = [
        Flight(
            flight_id="flight-1",
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
    
    print("\nTest 1: First round with departing flight...")
    loads, purchases = strategy.optimize(state, flights, airports, aircraft)
    
    print(f"Loads: {len(loads)}")
    print(f"Purchases: {len(purchases)}")
    
    if len(loads) == 0:
        print("FAIL: Expected at least 1 load decision!")
        return False
    
    # Check the load decision
    load = loads[0]
    print(f"Load decision for {load.flight_id}: {load.kits_per_class}")
    
    # Verify amounts don't exceed constraints
    expected_loads = {"FIRST": 5, "BUSINESS": 20, "PREMIUM_ECONOMY": 30, "ECONOMY": 100}
    for class_type, expected in expected_loads.items():
        actual = load.kits_per_class.get(class_type, 0)
        if actual != expected:
            print(f"FAIL: {class_type} expected {expected}, got {actual}")
            return False
        print(f"  ✓ {class_type}: {actual} (correct)")
    
    print("\nTest 2: Check inventory was updated...")
    hub_inv = strategy.inventory.get("HUB1", {})
    print(f"HUB inventory after load: {hub_inv}")
    
    # Verify inventory decreased
    if hub_inv.get("ECONOMY", 0) != 23651 - 100:
        print(f"FAIL: ECONOMY should be {23651 - 100}, got {hub_inv.get('ECONOMY', 0)}")
        return False
    print("  ✓ Inventory correctly decreased")
    
    print("\nTest 3: Run 100 rounds to check stability...")
    total_loads = 0
    total_purchases = 0
    
    for round_num in range(100):
        state.current_hour = round_num % 24
        state.current_day = round_num // 24
        
        # Update flight departure time
        flights[0] = Flight(
            flight_id=f"flight-{round_num}",
            flight_number="AB001",
            origin="HUB1",
            destination="OUT1",
            aircraft_type="A320",
            scheduled_departure=ReferenceHour(day=state.current_day, hour=state.current_hour),
            scheduled_arrival=ReferenceHour(day=state.current_day, hour=(state.current_hour + 2) % 24),
            planned_passengers={"FIRST": 5, "BUSINESS": 20, "PREMIUM_ECONOMY": 30, "ECONOMY": 100},
            actual_passengers={"FIRST": 5, "BUSINESS": 20, "PREMIUM_ECONOMY": 30, "ECONOMY": 100},
            planned_distance=1000.0,
            event_type="SCHEDULED",
        )
        
        loads, purchases = strategy.optimize(state, flights, airports, aircraft)
        total_loads += len(loads)
        total_purchases += len(purchases)
    
    print(f"  Total loads over 100 rounds: {total_loads}")
    print(f"  Total purchases over 100 rounds: {total_purchases}")
    print(f"  Final HUB inventory: {strategy.inventory.get('HUB1', {})}")
    
    if total_loads < 50:
        print("FAIL: Expected at least 50 load decisions over 100 rounds")
        return False
    
    print("\n✓ WorkingStrategy test PASSED!")
    return True

if __name__ == "__main__":
    success = test_working_strategy()
    sys.exit(0 if success else 1)
