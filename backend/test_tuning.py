"""
Test different loading percentages to find optimal cost.
"""
import sys
sys.path.insert(0, '.')

import csv
from collections import defaultdict
from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.airport import Airport
from models.aircraft import AircraftType
from models.kit import KitLoadDecision, KitPurchaseOrder
from config import KIT_DEFINITIONS

KIT_COSTS = {"FIRST": 500, "BUSINESS": 150, "PREMIUM_ECONOMY": 75, "ECONOMY": 50}
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

class TunableStrategy:
    def __init__(self, load_pct=1.0, purchase_interval=48):
        self.load_pct = load_pct  # Load only this % of passengers
        self.purchase_interval = purchase_interval
        self.round = 0
        self.inventory = {}
        self.hub_code = None
        self.hub_capacity = {}
        self.initialized = False
        
    def _init(self, airports):
        if self.initialized: return
        for code, ap in airports.items():
            self.inventory[code] = dict(ap.current_inventory)
            if ap.is_hub:
                self.hub_code = code
                self.hub_capacity = dict(ap.storage_capacity)
        self.initialized = True
    
    def optimize(self, state, flights, airports, aircraft_types):
        self.round += 1
        self._init(airports)
        current_hour = state.current_day * 24 + state.current_hour
        
        load_decisions = []
        for flight in flights:
            flight_hour = flight.scheduled_departure.day * 24 + flight.scheduled_departure.hour
            if flight_hour != current_hour: continue
            
            ac = aircraft_types.get(flight.aircraft_type)
            if not ac: continue
            
            pax = flight.actual_passengers or flight.planned_passengers
            kits = {}
            
            for cls in CLASS_TYPES:
                p = pax.get(cls, 0)
                if p == 0: continue
                
                # Load only load_pct of passengers
                target = int(p * self.load_pct)
                available = max(0, self.inventory.get(flight.origin, {}).get(cls, 0))
                capacity = ac.kit_capacity.get(cls, 0)
                load = min(target, available, capacity)
                
                if load > 0:
                    kits[cls] = load
                    self.inventory[flight.origin][cls] -= load
            
            if kits:
                load_decisions.append(KitLoadDecision(flight_id=flight.flight_id, kits_per_class=kits))
        
        # Purchase
        purchases = []
        if self.hub_code and self.round % self.purchase_interval == 1:
            kits_to_buy = {}
            for cls in CLASS_TYPES:
                stock = self.inventory.get(self.hub_code, {}).get(cls, 0)
                cap = self.hub_capacity.get(cls, 0)
                if stock < cap * 0.2 and cap - stock > 0:
                    kits_to_buy[cls] = min(int(cap * 0.1), cap - stock)
            
            if kits_to_buy:
                max_lead = max(int(KIT_DEFINITIONS[c]["lead_time"]) for c in kits_to_buy)
                eta = current_hour + max_lead + 6
                purchases.append(KitPurchaseOrder(
                    kits_per_class=kits_to_buy,
                    order_time=ReferenceHour(day=state.current_day, hour=state.current_hour),
                    expected_delivery=ReferenceHour(day=eta // 24, hour=eta % 24)
                ))
        
        return load_decisions, purchases

def run_test(load_pct, airports, aircraft, flights_by_hour):
    state = GameState(current_day=0, current_hour=0, airport_inventories={},
        pending_movements=[], flight_history=[], total_cost=0.0, in_process_kits={}, penalty_log=[])
    
    strategy = TunableStrategy(load_pct=load_pct, purchase_interval=72)
    totals = {k: 0.0 for k in ['movement', 'unfulfilled', 'other']}
    
    for r in range(720):
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
            ac = aircraft.get(flight.aircraft_type)
            fuel = ac.fuel_cost_per_km if ac else 0.08
            for cls, qty in load.kits_per_class.items():
                totals['movement'] += qty * KIT_WEIGHTS.get(cls, 10) * flight.planned_distance * fuel
                totals['other'] += qty * 5  # Approx loading + processing
        
        for flight in flights:
            pax = flight.actual_passengers or flight.planned_passengers
            load = next((l for l in loads if l.flight_id == flight.flight_id), None)
            loaded = load.kits_per_class if load else {}
            for cls, p in pax.items():
                unf = max(0, p - loaded.get(cls, 0))
                if unf > 0:
                    totals['unfulfilled'] += UNFULFILLED_FACTOR.get(cls, 500) * flight.planned_distance * unf / 1000
        
        for purchase in purchases:
            for cls, qty in purchase.kits_per_class.items():
                totals['other'] += qty * KIT_COSTS.get(cls, 100)
    
    return sum(totals.values())

def main():
    print("Loading data...")
    airports, aircraft, flights = load_data()
    
    print("\nTesting different load percentages:")
    print("-" * 50)
    
    best_pct, best_cost = 0, float('inf')
    
    for pct in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        cost = run_test(pct, airports, aircraft, flights)
        marker = " <-- BEST" if cost < best_cost else ""
        print(f"  {pct*100:5.0f}% loaded: ${cost:>15,.0f}{marker}")
        if cost < best_cost:
            best_cost = cost
            best_pct = pct
    
    print("-" * 50)
    print(f"OPTIMAL: {best_pct*100:.0f}% loading → ${best_cost:,.0f}")

if __name__ == "__main__":
    main()
