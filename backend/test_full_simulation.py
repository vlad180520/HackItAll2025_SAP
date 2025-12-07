"""
Full simulation test - verifies strategy handles:
1. Outbound flights (HUB -> outstation)
2. Return flights (outstation -> HUB)
3. Inventory tracking at both ends
4. Purchase timing
"""
import sys
sys.path.insert(0, '.')

from solution.strategies.working_strategy import WorkingStrategy
from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.airport import Airport
from models.aircraft import AircraftType

def test_full_simulation():
    print("=" * 60)
    print("FULL SIMULATION TEST")
    print("=" * 60)
    
    strategy = WorkingStrategy()
    
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
    
    # Realistic airports
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
    
    results = {
        "total_loads": 0,
        "total_purchases": 0,
        "negative_inventory": 0,
        "load_details": [],
    }
    
    # Simulate 48 hours (2 days)
    for hour in range(48):
        state.current_hour = hour % 24
        state.current_day = hour // 24
        
        flights = []
        
        # Every 4 hours: outbound flight HUB -> OUT1
        if hour % 4 == 0:
            flights.append(Flight(
                flight_id=f"outbound-{hour}",
                flight_number=f"AB{hour:03d}",
                origin="HUB1",
                destination="OUT1",
                aircraft_type="A320",
                scheduled_departure=ReferenceHour(day=state.current_day, hour=state.current_hour),
                scheduled_arrival=ReferenceHour(day=state.current_day, hour=(state.current_hour + 2) % 24),
                planned_passengers={"FIRST": 5, "BUSINESS": 15, "PREMIUM_ECONOMY": 25, "ECONOMY": 80},
                actual_passengers={"FIRST": 5, "BUSINESS": 15, "PREMIUM_ECONOMY": 25, "ECONOMY": 80},
                planned_distance=1000.0,
                event_type="SCHEDULED",
            ))
        
        # Every 4 hours (offset by 2): return flight OUT1 -> HUB
        if hour % 4 == 2:
            flights.append(Flight(
                flight_id=f"return-{hour}",
                flight_number=f"AB{hour:03d}R",
                origin="OUT1",
                destination="HUB1",
                aircraft_type="A320",
                scheduled_departure=ReferenceHour(day=state.current_day, hour=state.current_hour),
                scheduled_arrival=ReferenceHour(day=state.current_day, hour=(state.current_hour + 2) % 24),
                planned_passengers={"FIRST": 5, "BUSINESS": 15, "PREMIUM_ECONOMY": 25, "ECONOMY": 80},
                actual_passengers={"FIRST": 5, "BUSINESS": 15, "PREMIUM_ECONOMY": 25, "ECONOMY": 80},
                planned_distance=1000.0,
                event_type="SCHEDULED",
            ))
        
        loads, purchases = strategy.optimize(state, flights, airports, aircraft)
        
        results["total_loads"] += len(loads)
        results["total_purchases"] += len(purchases)
        
        for load in loads:
            results["load_details"].append({
                "hour": hour,
                "flight": load.flight_id,
                "kits": load.kits_per_class
            })
        
        # Check for negative inventory
        for airport_code, inv in strategy.inventory.items():
            for class_type, qty in inv.items():
                if qty < 0:
                    results["negative_inventory"] += 1
                    print(f"WARNING: Negative inventory at hour {hour}: {airport_code} {class_type} = {qty}")
    
    print(f"\n--- RESULTS ---")
    print(f"Total rounds: 48")
    print(f"Total load decisions: {results['total_loads']}")
    print(f"Total purchase orders: {results['total_purchases']}")
    print(f"Negative inventory occurrences: {results['negative_inventory']}")
    
    print(f"\nFinal HUB inventory: {strategy.inventory.get('HUB1', {})}")
    print(f"Final OUT1 inventory: {strategy.inventory.get('OUT1', {})}")
    
    # Verify no negative inventory
    if results["negative_inventory"] > 0:
        print("\nFAIL: Had negative inventory!")
        return False
    
    # Verify we made some decisions
    if results["total_loads"] == 0:
        print("\nFAIL: No load decisions made!")
        return False
    
    print("\n✓ Full simulation test PASSED!")
    return True

if __name__ == "__main__":
    success = test_full_simulation()
    sys.exit(0 if success else 1)
