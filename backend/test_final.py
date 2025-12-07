"""Test final strategy"""
import sys
sys.path.insert(0, '.')

import csv
from collections import defaultdict
from solution.strategies.final_strategy import FinalStrategy
from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.airport import Airport
from models.aircraft import AircraftType

KIT_COSTS = {"FIRST": 500, "BUSINESS": 150, "PREMIUM_ECONOMY": 75, "ECONOMY": 50}
KIT_WEIGHTS = {"FIRST": 15, "BUSINESS": 12, "PREMIUM_ECONOMY": 8, "ECONOMY": 5}
UNFULFILLED_FACTOR = {"FIRST": 2226, "BUSINESS": 1113, "PREMIUM_ECONOMY": 557, "ECONOMY": 278}

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
                'flight_id': row['id'], 'flight_number': row['flight_number'],
                'origin': airport_id_map.get(row['origin_airport_id']),
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

def run_simulation(strategy, airports, aircraft, flights_by_hour, rounds=720):
    state = GameState(current_day=0, current_hour=0, airport_inventories={},
        pending_movements=[], flight_history=[], total_cost=0.0, in_process_kits={}, penalty_log=[])
    
    totals = {k: 0.0 for k in ['loading', 'movement', 'processing', 'purchase', 'unfulfilled']}
    counts = {'loaded': 0, 'purchased': 0, 'unfulfilled': 0}
    
    for r in range(rounds):
        state.current_day, state.current_hour = r // 24, r % 24
        flight_data = flights_by_hour.get((state.current_day, state.current_hour), [])
        flights = [Flight(
            flight_id=fd['flight_id'], flight_number=fd['flight_number'],
            origin=fd['origin'], destination=fd['destination'], aircraft_type=fd['aircraft_type'],
            scheduled_departure=ReferenceHour(day=state.current_day, hour=fd['departure_hour']),
            scheduled_arrival=ReferenceHour(day=fd['arrival_day'], hour=fd['arrival_hour']),
            planned_passengers=fd['passengers'], actual_passengers=fd['passengers'],
            planned_distance=fd['distance'], event_type="SCHEDULED"
        ) for fd in flight_data]
        
        loads, purchases = strategy.optimize(state, flights, airports, aircraft)
        
        for load in loads:
            flight = next((f for f in flights if f.flight_id == load.flight_id), None)
            if not flight: continue
            origin_ap, dest_ap = airports.get(flight.origin), airports.get(flight.destination)
            ac = aircraft.get(flight.aircraft_type)
            fuel = ac.fuel_cost_per_km if ac else 0.08
            for cls, qty in load.kits_per_class.items():
                totals['loading'] += qty * (origin_ap.loading_costs.get(cls, 1) if origin_ap else 1)
                totals['movement'] += qty * KIT_WEIGHTS.get(cls, 10) * flight.planned_distance * fuel
                totals['processing'] += qty * (dest_ap.processing_costs.get(cls, 5) if dest_ap else 5)
                counts['loaded'] += qty
        
        for flight in flights:
            pax = flight.actual_passengers or flight.planned_passengers
            load = next((l for l in loads if l.flight_id == flight.flight_id), None)
            loaded = load.kits_per_class if load else {}
            for cls, p in pax.items():
                unf = max(0, p - loaded.get(cls, 0))
                if unf > 0:
                    totals['unfulfilled'] += UNFULFILLED_FACTOR.get(cls, 500) * flight.planned_distance * unf / 1000
                    counts['unfulfilled'] += unf
        
        for purchase in purchases:
            for cls, qty in purchase.kits_per_class.items():
                totals['purchase'] += qty * KIT_COSTS.get(cls, 100)
                counts['purchased'] += qty
    
    totals['total'] = sum(totals.values())
    return totals, counts

def main():
    print("Loading data...")
    airports, aircraft, flights = load_data()
    
    print("Running FinalStrategy (720 rounds)...\n")
    strategy = FinalStrategy()
    costs, counts = run_simulation(strategy, airports, aircraft, flights)
    
    print("=" * 55)
    print("FINAL STRATEGY - COST BREAKDOWN")
    print("=" * 55)
    print(f"Loading cost:        ${costs['loading']:>15,.0f}")
    print(f"Movement cost:       ${costs['movement']:>15,.0f}")
    print(f"Processing cost:     ${costs['processing']:>15,.0f}")
    print(f"Purchase cost:       ${costs['purchase']:>15,.0f}")
    print(f"Unfulfilled penalty: ${costs['unfulfilled']:>15,.0f}")
    print("-" * 55)
    print(f"TOTAL:               ${costs['total']:>15,.0f}")
    print("=" * 55)
    print(f"\nKits loaded: {counts['loaded']:,}")
    print(f"Kits purchased: {counts['purchased']:,}")
    print(f"Unfulfilled: {counts['unfulfilled']:,}")
    
    print("\n" + "=" * 55)
    print("ANALYSIS")
    print("=" * 55)
    baseline = 1_656_193_491
    print(f"Theoretical minimum (0% load): ${baseline:,}")
    print(f"This result:                   ${costs['total']:,.0f}")
    savings = baseline - costs['total']
    print(f"Savings from selective load:   ${savings:,.0f}")
    print("=" * 55)

if __name__ == "__main__":
    main()
