"""Test time-expanded MILP with purchases and lead times."""

import sys
import logging
from solution.decision_maker import DecisionMaker
from solution.config import SolutionConfig
from models.game_state import GameState, ReferenceHour
from models.flight import Flight
from models.airport import Airport
from models.aircraft import AircraftType

logging.basicConfig(level=logging.INFO)

def test_purchase_timing():
    """Test that purchases respect lead times."""
    print("=" * 60)
    print("Testing Purchase Timing with Lead Times")
    print("=" * 60)
    
    dm = DecisionMaker(SolutionConfig.default())
    
    # Create state with LOW inventory at HUB
    state = GameState(
        current_day=0,
        current_hour=0,
        airport_inventories={
            "HUB1": {"ECONOMY": 10, "BUSINESS": 5, "PREMIUM_ECONOMY": 5, "FIRST": 2},
        },
        in_process_kits={},
        pending_movements=[],
        total_cost=0.0,
        penalty_log=[],
        flight_history=[]
    )
    
    # Create flights requiring more inventory than available
    # Flights at hour 0, 2, 4, 6 (need to purchase to cover later flights)
    flights = [
        Flight(
            flight_id=f"FL{i:03d}",
            flight_number=f"TS{i:03d}",
            origin="HUB1",
            destination="OUT1",
            scheduled_departure=ReferenceHour(day=0, hour=i*2),
            scheduled_arrival=ReferenceHour(day=0, hour=i*2+2),
            planned_passengers={"ECONOMY": 20, "BUSINESS": 5, "PREMIUM_ECONOMY": 5, "FIRST": 2},
            planned_distance=1000.0,
            aircraft_type="A320",
            event_type="SCHEDULED"
        )
        for i in range(5)  # 5 flights
    ]
    
    airports = {
        "HUB1": Airport(
            code="HUB1",
            name="Hub",
            is_hub=True,
            storage_capacity={"ECONOMY": 500, "BUSINESS": 200, "PREMIUM_ECONOMY": 200, "FIRST": 100},
            loading_costs={"ECONOMY": 1.0, "BUSINESS": 1.5, "PREMIUM_ECONOMY": 1.5, "FIRST": 2.0},
            processing_costs={"ECONOMY": 0.5, "BUSINESS": 0.8, "PREMIUM_ECONOMY": 0.8, "FIRST": 1.0},
            processing_times={"ECONOMY": 1, "BUSINESS": 2, "PREMIUM_ECONOMY": 2, "FIRST": 3},
        ),
        "OUT1": Airport(
            code="OUT1",
            name="Outstation",
            is_hub=False,
            storage_capacity={"ECONOMY": 100, "BUSINESS": 50, "PREMIUM_ECONOMY": 50, "FIRST": 20},
            loading_costs={"ECONOMY": 1.5, "BUSINESS": 2.0, "PREMIUM_ECONOMY": 2.0, "FIRST": 3.0},
            processing_costs={"ECONOMY": 1.0, "BUSINESS": 1.5, "PREMIUM_ECONOMY": 1.5, "FIRST": 2.0},
            processing_times={"ECONOMY": 1, "BUSINESS": 2, "PREMIUM_ECONOMY": 2, "FIRST": 3},
        )
    }
    
    aircraft_types = {
        "A320": AircraftType(
            type_code="A320",
            passenger_capacity={"ECONOMY": 120, "BUSINESS": 20, "PREMIUM_ECONOMY": 30, "FIRST": 10},
            kit_capacity={"ECONOMY": 120, "BUSINESS": 20, "PREMIUM_ECONOMY": 30, "FIRST": 10},
            fuel_cost_per_km=0.5
        )
    }
    
    print(f"\nInitial HUB inventory: {state.airport_inventories['HUB1']}")
    print(f"Number of flights in next 10h: {len([f for f in flights if f.scheduled_departure.to_hours() < 10])}")
    print(f"Total demand: ECONOMY={20*5}, BUSINESS={5*5}, etc.")
    print()
    
    loads, purchases = dm.make_decisions(state, flights, airports, aircraft_types)
    
    print(f"\n✓ Decisions made:")
    print(f"  Loads: {len(loads)}")
    for load in loads:
        print(f"    {load.flight_id}: {load.kits_per_class}")
    
    print(f"  Purchases: {len(purchases)}")
    for purchase in purchases:
        print(f"    Ordered: {purchase.kits_per_class}")
        print(f"    Order time: Day {purchase.order_time.day}, Hour {purchase.order_time.hour}")
        print(f"    Delivery: Day {purchase.expected_delivery.day}, Hour {purchase.expected_delivery.hour}")
        
        # Verify lead time
        order_hours = purchase.order_time.to_hours()
        delivery_hours = purchase.expected_delivery.to_hours()
        lead_time = delivery_hours - order_hours
        print(f"    Lead time: {lead_time} hours")
        
        if lead_time < 12:
            print(f"    ✗ ERROR: Lead time too short!")
            return 1
        else:
            print(f"    ✓ Lead time valid")
    
    # Check that first flight can be loaded despite low inventory
    first_load = next((l for l in loads if l.flight_id == "FL000"), None)
    if first_load:
        print(f"\n✓ First flight loaded successfully: {first_load.kits_per_class}")
    else:
        print(f"\n✗ ERROR: First flight not loaded!")
        return 1
    
    # Check that purchases were made for future demand
    if purchases:
        print(f"\n✓ Purchases made to cover future demand")
    else:
        print(f"\nℹ No purchases (may be acceptable if inventory sufficient)")
    
    print("\n" + "=" * 60)
    print("✓✓✓ TIMING TEST PASSED ✓✓✓")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(test_purchase_timing())
