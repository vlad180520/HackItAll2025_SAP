"""Quick integration test for MILP strategy."""

import sys
import logging
from solution.decision_maker import DecisionMaker
from solution.config import SolutionConfig
from models.game_state import GameState, ReferenceHour
from models.flight import Flight
from models.airport import Airport
from models.aircraft import AircraftType

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_milp_integration():
    """Test MILP strategy integration."""
    print("=" * 60)
    print("MILP Strategy Integration Test")
    print("=" * 60)
    
    # Create DecisionMaker
    config = SolutionConfig.default()
    dm = DecisionMaker(config)
    print(f"✓ DecisionMaker created with strategy: {type(dm.strategy).__name__}")
    print(f"  - Horizon: {dm.strategy.horizon_hours}h")
    print(f"  - Timeout: {dm.strategy.solver_timeout_s}s")
    
    # Create minimal test state
    state = GameState(
        current_day=0,
        current_hour=6,
        airport_inventories={
            "HUB1": {"ECONOMY": 100, "BUSINESS": 50, "PREMIUM_ECONOMY": 50, "FIRST": 20},
            "OUT1": {"ECONOMY": 10, "BUSINESS": 5, "PREMIUM_ECONOMY": 5, "FIRST": 2},
        },
        in_process_kits={},
        pending_movements=[],
        total_cost=0.0,
        penalty_log=[],
        flight_history=[]
    )
    print(f"✓ Test state created (Day {state.current_day}, Hour {state.current_hour})")
    
    # Create test flight
    flights = [
        Flight(
            flight_id="TEST001",
            flight_number="TS001",
            origin="HUB1",
            destination="OUT1",
            scheduled_departure=ReferenceHour(day=0, hour=6),
            scheduled_arrival=ReferenceHour(day=0, hour=8),
            planned_passengers={"ECONOMY": 50, "BUSINESS": 10, "PREMIUM_ECONOMY": 10, "FIRST": 5},
            planned_distance=500.0,
            aircraft_type="A320",
            event_type="SCHEDULED"
        )
    ]
    print(f"✓ Test flight created: {flights[0].flight_id} ({flights[0].origin} → {flights[0].destination})")
    
    # Create airports
    airports = {
        "HUB1": Airport(
            code="HUB1",
            name="Hub Airport",
            is_hub=True,
            storage_capacity={"ECONOMY": 500, "BUSINESS": 300, "PREMIUM_ECONOMY": 300, "FIRST": 100},
            loading_costs={"ECONOMY": 1.0, "BUSINESS": 1.5, "PREMIUM_ECONOMY": 1.5, "FIRST": 2.0},
            processing_costs={"ECONOMY": 0.5, "BUSINESS": 0.8, "PREMIUM_ECONOMY": 0.8, "FIRST": 1.0},
            processing_times={"ECONOMY": 1, "BUSINESS": 2, "PREMIUM_ECONOMY": 2, "FIRST": 3},
            current_inventory={"ECONOMY": 100, "BUSINESS": 50, "PREMIUM_ECONOMY": 50, "FIRST": 20}
        ),
        "OUT1": Airport(
            code="OUT1",
            name="Outstation 1",
            is_hub=False,
            storage_capacity={"ECONOMY": 100, "BUSINESS": 50, "PREMIUM_ECONOMY": 50, "FIRST": 20},
            loading_costs={"ECONOMY": 1.5, "BUSINESS": 2.0, "PREMIUM_ECONOMY": 2.0, "FIRST": 3.0},
            processing_costs={"ECONOMY": 1.0, "BUSINESS": 1.5, "PREMIUM_ECONOMY": 1.5, "FIRST": 2.0},
            processing_times={"ECONOMY": 1, "BUSINESS": 2, "PREMIUM_ECONOMY": 2, "FIRST": 3},
            current_inventory={"ECONOMY": 10, "BUSINESS": 5, "PREMIUM_ECONOMY": 5, "FIRST": 2}
        )
    }
    print(f"✓ Airports created: {', '.join(airports.keys())}")
    
    # Create aircraft
    aircraft_types = {
        "A320": AircraftType(
            type_code="A320",
            passenger_capacity={"ECONOMY": 120, "BUSINESS": 20, "PREMIUM_ECONOMY": 30, "FIRST": 10},
            kit_capacity={"ECONOMY": 120, "BUSINESS": 20, "PREMIUM_ECONOMY": 30, "FIRST": 10},
            fuel_cost_per_km=0.5
        )
    }
    print(f"✓ Aircraft types created: {', '.join(aircraft_types.keys())}")
    
    # Run optimization
    print("\n" + "=" * 60)
    print("Running MILP optimization...")
    print("=" * 60)
    
    try:
        loads, purchases = dm.make_decisions(state, flights, airports, aircraft_types)
        
        print("\n✓ Optimization completed successfully!")
        print(f"\nLoad Decisions: {len(loads)}")
        for load in loads:
            print(f"  - Flight {load.flight_id}: {load.kits_per_class}")
        
        print(f"\nPurchase Orders: {len(purchases)}")
        for purchase in purchases:
            print(f"  - Order: {purchase.kits_per_class}")
            print(f"    Ordered at: Day {purchase.order_time.day}, Hour {purchase.order_time.hour}")
            print(f"    Delivery at: Day {purchase.expected_delivery.day}, Hour {purchase.expected_delivery.hour}")
        
        # Validation
        print("\n" + "=" * 60)
        print("Validation")
        print("=" * 60)
        
        validation_passed = True
        
        # Check loads
        if loads:
            for load in loads:
                for cls, qty in load.kits_per_class.items():
                    capacity = aircraft_types["A320"].kit_capacity[cls]
                    if qty > capacity:
                        print(f"✗ ERROR: Load exceeds capacity for {cls}: {qty} > {capacity}")
                        validation_passed = False
                    else:
                        print(f"✓ Load within capacity for {cls}: {qty} <= {capacity}")
        else:
            print("ℹ No load decisions")
        
        # Check purchases
        if purchases:
            for purchase in purchases:
                for cls, qty in purchase.kits_per_class.items():
                    if qty < 0:
                        print(f"✗ ERROR: Negative purchase for {cls}: {qty}")
                        validation_passed = False
                    else:
                        print(f"✓ Purchase valid for {cls}: {qty}")
        else:
            print("ℹ No purchase orders")
        
        if validation_passed:
            print("\n" + "=" * 60)
            print("✓✓✓ ALL TESTS PASSED ✓✓✓")
            print("=" * 60)
            return 0
        else:
            print("\n" + "=" * 60)
            print("✗✗✗ VALIDATION FAILED ✗✗✗")
            print("=" * 60)
            return 1
            
    except Exception as e:
        print(f"\n✗ ERROR during optimization: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(test_milp_integration())
