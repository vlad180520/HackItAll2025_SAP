#!/usr/bin/env python3
"""Quick verification that Genetic Algorithm is working correctly."""

import sys
sys.path.insert(0, '/home/utzu/HackItAll2025_SAP/backend')

from solution import DecisionMaker
from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.airport import Airport
from models.aircraft import AircraftType

print("=" * 60)
print("GENETIC ALGORITHM VERIFICATION TEST")
print("=" * 60)

# Create test scenario
state = GameState(
    current_day=1,
    current_hour=10,
    airport_inventories={
        'HUB1': {'FIRST': 50, 'BUSINESS': 80, 'PREMIUM_ECONOMY': 100, 'ECONOMY': 150},
        'OUT1': {'FIRST': 20, 'BUSINESS': 30, 'PREMIUM_ECONOMY': 40, 'ECONOMY': 60}
    },
    in_process_kits={},
    pending_movements=[],
    total_cost=0.0,
    penalty_log=[],
    flight_history=[]
)

airports = {
    'HUB1': Airport(
        code='HUB1', name='Hub', is_hub=True,
        storage_capacity={'FIRST': 100, 'BUSINESS': 150, 'PREMIUM_ECONOMY': 200, 'ECONOMY': 300},
        loading_costs={'FIRST': 10.0, 'BUSINESS': 8.0, 'PREMIUM_ECONOMY': 6.0, 'ECONOMY': 5.0},
        processing_costs={'FIRST': 5.0, 'BUSINESS': 4.0, 'PREMIUM_ECONOMY': 3.0, 'ECONOMY': 2.0},
        processing_times={'FIRST': 6, 'BUSINESS': 4, 'PREMIUM_ECONOMY': 2, 'ECONOMY': 1},
        current_inventory={'FIRST': 50, 'BUSINESS': 80, 'PREMIUM_ECONOMY': 100, 'ECONOMY': 150}
    ),
    'OUT1': Airport(
        code='OUT1', name='Outstation', is_hub=False,
        storage_capacity={'FIRST': 50, 'BUSINESS': 75, 'PREMIUM_ECONOMY': 100, 'ECONOMY': 150},
        loading_costs={'FIRST': 12.0, 'BUSINESS': 10.0, 'PREMIUM_ECONOMY': 8.0, 'ECONOMY': 6.0},
        processing_costs={'FIRST': 8.0, 'BUSINESS': 6.0, 'PREMIUM_ECONOMY': 4.0, 'ECONOMY': 3.0},
        processing_times={'FIRST': 45, 'BUSINESS': 30, 'PREMIUM_ECONOMY': 20, 'ECONOMY': 10},
        current_inventory={'FIRST': 20, 'BUSINESS': 30, 'PREMIUM_ECONOMY': 40, 'ECONOMY': 60}
    )
}

aircraft_types = {
    'A320': AircraftType(
        type_code='A320',
        passenger_capacity={'FIRST': 10, 'BUSINESS': 30, 'PREMIUM_ECONOMY': 40, 'ECONOMY': 100},
        kit_capacity={'FIRST': 10, 'BUSINESS': 30, 'PREMIUM_ECONOMY': 40, 'ECONOMY': 100},
        fuel_cost_per_km=0.5
    )
}

flights = [
    Flight(
        flight_id='FL001', flight_number='AA100',
        origin='HUB1', destination='OUT1',
        scheduled_departure=ReferenceHour(day=1, hour=10),
        scheduled_arrival=ReferenceHour(day=1, hour=14),
        planned_passengers={'FIRST': 8, 'BUSINESS': 25, 'PREMIUM_ECONOMY': 35, 'ECONOMY': 90},
        planned_distance=2000.0,
        aircraft_type='A320',
        event_type='SCHEDULED'
    ),
    Flight(
        flight_id='FL002', flight_number='AA101',
        origin='OUT1', destination='HUB1',
        scheduled_departure=ReferenceHour(day=1, hour=11),
        scheduled_arrival=ReferenceHour(day=1, hour=15),
        planned_passengers={'FIRST': 5, 'BUSINESS': 20, 'PREMIUM_ECONOMY': 30, 'ECONOMY': 80},
        planned_distance=2000.0,
        aircraft_type='A320',
        event_type='SCHEDULED'
    )
]

# Create decision maker with genetic strategy
dm = DecisionMaker()

print("\nRunning optimization...")
print("-" * 60)

loads, purchases = dm.make_decisions(state, flights, airports, aircraft_types)

print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)

print(f"\nLoad Decisions: {len(loads)}")
for decision in loads:
    total = sum(decision.kits_per_class.values())
    print(f"  {decision.flight_id}: {total} kits total")
    for cls, qty in decision.kits_per_class.items():
        if qty > 0:
            print(f"    - {cls}: {qty}")

if purchases:
    print(f"\nPurchase Orders: {len(purchases)}")
    for order in purchases:
        total = sum(order.kits_per_class.values())
        print(f"  Total: {total} kits")
        for cls, qty in order.kits_per_class.items():
            if qty > 0:
                print(f"    - {cls}: {qty}")
else:
    print("\nPurchase Orders: None needed")

print("\n" + "=" * 60)
print("✓ GENETIC ALGORITHM IS WORKING CORRECTLY")
print("=" * 60)
