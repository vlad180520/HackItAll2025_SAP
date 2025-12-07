"""Fine-tune threshold"""
import sys
sys.path.insert(0, '.')

import csv
from collections import defaultdict
from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.airport import Airport
from models.aircraft import AircraftType
from models.kit import KitLoadDecision

KIT_WEIGHTS = {"FIRST": 15, "BUSINESS": 12, "PREMIUM_ECONOMY": 8, "ECONOMY": 5}
UNFULFILLED_FACTOR = {"FIRST": 2226, "BUSINESS": 1113, "PREMIUM_ECONOMY": 557, "ECONOMY": 278}
CLASS_TYPES = ["FIRST", "BUSINESS", "PREMIUM_ECONOMY", "ECONOMY"]

def load_data():
    airports, airport_id_map = {}, {}
    with open("../HackitAll2025-main/eval-platform/src/main/resources/liquibase/data/airports_with_stocks.csv", 'r') as f:
        for row in csv.DictReader(f, delimiter=';'):
            code = row['code']
            airport_id_map[row['id']] = code
            airports[code] = Airport(
                code=code, name=row['name'], is_hub=(code == "HUB1"),
                processing_times={"FIRST": int(row['first_processing_time']), "BUSINESS": int(row['business_processing_time']),
                    "PREMIUM_ECONOMY": int(row['premium_economy_processing_time']), "ECONOMY": int(row['economy_processing_time'])},
                processing_costs={"FIRST": float(row['first_processing_cost']), "BUSINESS": float(row['business_processing_cost']),
                    "PREMIUM_ECONOMY": float(row['premium_economy_processing_cost']), "ECONOMY": float(row['economy_processing_cost'])},
                loading_costs={"FIRST": float(row['first_loading_cost']), "BUSINESS": float(row['business_loading_cost']),
                    "PREMIUM_ECONOMY": float(row['premium_economy_loading_cost']), "ECONOMY": float(row['economy_loading_cost'])},
                current_inventory={"FIRST": int(row['initial_fc_stock']), "BUSINESS": int(row['initial_bc_stock']),
                    "PREMIUM_ECONOMY": int(row['initial_pe_stock']), "ECONOMY": int(row['initial_ec_stock'])},
                storage_capacity={"FIRST": int(row['capacity_fc']), "BUSINESS": int(row['capacity_bc']),
                    "PREMIUM_ECONOMY": int(row['capacity_pe']), "ECONOMY": int(row['capacity_ec'])},
            )
    
    aircraft, aircraft_id_map = {}, {}
    with open("../HackitAll2025-main/eval-platform/src/main/resources/liquibase/data/aircraft_types.csv", 'r') as f:
        for row in csv.DictReader(f, delimiter=';'):
            code = row['type_code']
            aircraft_id_map[row['id']] = code
            aircraft[code] = AircraftType(
                type_code=code, fuel_cost_per_km=float(row['cost_per_kg_per_km']),
                kit_capacity={"FIRST": int(row.get('first_class_kits_capacity', 0) or 0), "BUSINESS": int(row.get('business_kits_capacity', 0) or 0),
                    "PREMIUM_ECONOMY": int(row.get('premium_economy_kits_capacity', 0) or 0), "ECONOMY": int(row.get('economy_kits_capacity', 0) or 0)},
                passenger_capacity={"FIRST": int(row.get('first_class_seats', 0) or 0), "BUSINESS": int(row.get('business_seats', 0) or 0),
                    "PREMIUM_ECONOMY": int(row.get('premium_economy_seats', 0) or 0), "ECONOMY": int(row.get('economy_seats', 0) or 0)},
            )
    
    flights_by_hour = defaultdict(list)
    with open("../HackitAll2025-main/eval-platform/src/main/resources/liquibase/data/flights.csv", 'r') as f:
        for row in csv.DictReader(f, delimiter=';'):
            day = int(row['scheduled_depart_day'])
            if day >= 30: continue
            hour = int(row['scheduled_depart_hour'])
            flights_by_hour[(day, hour)].append({
                'flight_id': row['id'], 'origin': airport_id_map.get(row['origin_airport_id']),
                'destination': airport_id_map.get(row['destination_airport_id']),
                'aircraft_type': aircraft_id_map.get(row['sched_aircraft_type_id']),
                'departure_hour': hour, 'arrival_day': int(row['scheduled_arrival_day']),
                'arrival_hour': int(row['scheduled_arrival_hour']), 'distance': float(row['distance']),
                'passengers': {"FIRST": int(row.get('actual_first_passengers', 0) or 0),
                    "BUSINESS": int(row.get('actual_business_passengers', 0) or 0),
                    "PREMIUM_ECONOMY": int(row.get('actual_premium_economy_passengers', 0) or 0),
                    "ECONOMY": int(row.get('actual_economy_passengers', 0) or 0)}
            })
    return airports, aircraft, flights_by_hour

def run_test(threshold, airports, aircraft, flights_by_hour):
    inventory = {code: dict(ap.current_inventory) for code, ap in airports.items()}
    total = 0.0
    
    for r in range(720):
        day, hour = r // 24, r % 24
        flight_data = flights_by_hour.get((day, hour), [])
        
        for fd in flight_data:
            ac = aircraft.get(fd['aircraft_type'])
            if not ac: continue
            
            origin_ap = airports.get(fd['origin'])
            dest_ap = airports.get(fd['destination'])
            fuel = ac.fuel_cost_per_km
            dist = fd['distance']
            pax = fd['passengers']
            
            for cls in CLASS_TYPES:
                p = pax.get(cls, 0)
                if p == 0: continue
                
                # Check if should load
                weight = KIT_WEIGHTS.get(cls, 10)
                movement = weight * dist * fuel
                unfulfilled_penalty = UNFULFILLED_FACTOR.get(cls, 500) * dist / 1000
                
                if movement < unfulfilled_penalty * threshold:
                    available = max(0, inventory.get(fd['origin'], {}).get(cls, 0))
                    capacity = ac.kit_capacity.get(cls, 0)
                    load = min(p, available, capacity)
                    
                    if load > 0:
                        inventory[fd['origin']][cls] -= load
                        # Costs
                        total += load * (origin_ap.loading_costs.get(cls, 1) if origin_ap else 1)
                        total += load * weight * dist * fuel
                        total += load * (dest_ap.processing_costs.get(cls, 5) if dest_ap else 5)
                        p -= load
                
                # Unfulfilled
                if p > 0:
                    total += UNFULFILLED_FACTOR.get(cls, 500) * dist * p / 1000
    
    return total

def main():
    airports, aircraft, flights = load_data()
    
    print("Fine-tuning threshold (0.80 to 1.05):")
    print("-" * 45)
    
    best_cost = float('inf')
    best_t = 0
    
    for t in [0.80, 0.85, 0.88, 0.90, 0.92, 0.95, 0.98, 1.00, 1.02, 1.05]:
        cost = run_test(t, airports, aircraft, flights)
        marker = " <-- BEST" if cost < best_cost else ""
        print(f"  {t:.2f}: ${cost:>15,.0f}{marker}")
        if cost < best_cost:
            best_cost = cost
            best_t = t
    
    print("-" * 45)
    print(f"OPTIMAL: threshold={best_t:.2f} → ${best_cost:,.0f}")

if __name__ == "__main__":
    main()
