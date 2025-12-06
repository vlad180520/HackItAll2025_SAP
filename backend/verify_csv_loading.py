#!/usr/bin/env python3
"""Comprehensive CSV loading verification test."""

import sys
sys.path.insert(0, '/home/utzu/HackItAll2025_SAP/backend')

from config import Config, AIRPORTS_CSV, AIRCRAFT_TYPES_CSV, FLIGHT_PLAN_CSV, CLASS_TYPES
from data_loader import load_airports, load_aircraft_types

print("=" * 70)
print("CSV LOADING VERIFICATION TEST")
print("=" * 70)

config = Config()

# Test 1: Airports CSV
print("\n[1] Loading Airports from:", AIRPORTS_CSV)
print("-" * 70)
try:
    airports = load_airports(AIRPORTS_CSV, config)
    print(f"✓ Successfully loaded {len(airports)} airports")
    
    # Find hub
    hubs = [code for code, a in airports.items() if a.is_hub]
    print(f"✓ Hub airports: {hubs}")
    
    if hubs:
        hub_code = hubs[0]
        hub = airports[hub_code]
        print(f"\n  Hub Details ({hub_code}):")
        print(f"    - Name: {hub.name}")
        print(f"    - Storage capacity: {hub.storage_capacity}")
        print(f"    - Current inventory: {hub.current_inventory}")
        print(f"    - Loading costs: {hub.loading_costs}")
        print(f"    - Processing times: {hub.processing_times}")
    
    # Sample outstation
    outstations = [code for code, a in airports.items() if not a.is_hub]
    if outstations:
        out_code = outstations[0]
        out = airports[out_code]
        print(f"\n  Sample Outstation ({out_code}):")
        print(f"    - Name: {out.name}")
        print(f"    - Current inventory: {out.current_inventory}")
        print(f"    - Processing times: {out.processing_times}")
    
    # Verify all classes present
    print(f"\n  Verification:")
    for class_type in CLASS_TYPES:
        has_capacity = all(class_type in a.storage_capacity for a in airports.values())
        has_inventory = all(class_type in a.current_inventory for a in airports.values())
        print(f"    - {class_type}: capacity={has_capacity}, inventory={has_inventory}")
    
except Exception as e:
    print(f"✗ ERROR loading airports: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Aircraft Types CSV
print("\n[2] Loading Aircraft Types from:", AIRCRAFT_TYPES_CSV)
print("-" * 70)
try:
    aircraft = load_aircraft_types(AIRCRAFT_TYPES_CSV)
    print(f"✓ Successfully loaded {len(aircraft)} aircraft types")
    
    # Show details for each type
    for i, (type_code, ac) in enumerate(aircraft.items(), 1):
        print(f"\n  Aircraft {i}: {type_code}")
        print(f"    - Passenger capacity: {ac.passenger_capacity}")
        print(f"    - Kit capacity: {ac.kit_capacity}")
        print(f"    - Fuel cost per km: {ac.fuel_cost_per_km}")
        
        # Verify all classes
        for class_type in CLASS_TYPES:
            p_cap = ac.passenger_capacity.get(class_type, 0)
            k_cap = ac.kit_capacity.get(class_type, 0)
            print(f"      {class_type}: passengers={p_cap}, kits={k_cap}")
    
except Exception as e:
    print(f"✗ ERROR loading aircraft types: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Integration check
print("\n[3] Integration Verification")
print("-" * 70)
try:
    from solution import DecisionMaker
    dm = DecisionMaker()
    print(f"✓ DecisionMaker initialized successfully")
    print(f"✓ Strategy type: {type(dm.strategy).__name__}")
    print(f"✓ GA Config: pop={dm.strategy.ga_config.population_size}, gens={dm.strategy.ga_config.num_generations}")
    
except Exception as e:
    print(f"✗ ERROR in integration: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("CSV VERIFICATION COMPLETE")
print("=" * 70)
print("\nSummary:")
print(f"  - Airports loaded: {len(airports) if 'airports' in locals() else 'FAILED'}")
print(f"  - Aircraft types loaded: {len(aircraft) if 'aircraft' in locals() else 'FAILED'}")
print(f"  - Hubs found: {len(hubs) if 'hubs' in locals() else 'FAILED'}")
print(f"  - DecisionMaker: {'OK' if 'dm' in locals() else 'FAILED'}")
print("=" * 70)
