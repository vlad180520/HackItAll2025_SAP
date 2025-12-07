"""
Detailed cost analysis to understand where costs come from.
"""
import sys
sys.path.insert(0, '.')

import csv
from collections import defaultdict

UNFULFILLED_FACTOR = {"FIRST": 2226, "BUSINESS": 1113, "PREMIUM_ECONOMY": 557, "ECONOMY": 278}

def main():
    # Count total passengers
    total_pax = {"FIRST": 0, "BUSINESS": 0, "PREMIUM_ECONOMY": 0, "ECONOMY": 0}
    total_flights = 0
    total_unfulfilled_cost = 0.0
    
    with open("../HackitAll2025-main/eval-platform/src/main/resources/liquibase/data/flights.csv", 'r') as f:
        for row in csv.DictReader(f, delimiter=';'):
            day = int(row['scheduled_depart_day'])
            if day >= 30: continue
            
            total_flights += 1
            distance = float(row['distance'])
            
            for cls, col in [("FIRST", "actual_first_passengers"), 
                            ("BUSINESS", "actual_business_passengers"),
                            ("PREMIUM_ECONOMY", "actual_premium_economy_passengers"),
                            ("ECONOMY", "actual_economy_passengers")]:
                pax = int(row.get(col, 0) or 0)
                total_pax[cls] += pax
                
                # If NO kits loaded, unfulfilled penalty:
                penalty = UNFULFILLED_FACTOR[cls] * distance * pax / 1000
                total_unfulfilled_cost += penalty
    
    print("=" * 60)
    print("PASSENGER ANALYSIS (720 rounds = 30 days)")
    print("=" * 60)
    print(f"Total flights: {total_flights:,}")
    print(f"\nPassengers by class:")
    for cls in ["FIRST", "BUSINESS", "PREMIUM_ECONOMY", "ECONOMY"]:
        print(f"  {cls}: {total_pax[cls]:,}")
    print(f"\nTotal passengers: {sum(total_pax.values()):,}")
    
    print("\n" + "=" * 60)
    print("COST IF NO KITS LOADED (baseline)")
    print("=" * 60)
    print(f"Total unfulfilled penalty: ${total_unfulfilled_cost:,.2f}")
    
    # Also calculate if we load all kits
    # Movement cost approx: weight * distance * fuel_cost * kits
    # Average weight ~7kg, average fuel ~0.08
    avg_distance = 1500  # approximate
    total_kits = sum(total_pax.values())
    avg_weight = (15 * total_pax["FIRST"] + 12 * total_pax["BUSINESS"] + 
                  8 * total_pax["PREMIUM_ECONOMY"] + 5 * total_pax["ECONOMY"]) / total_kits
    
    # We need actual per-flight calculation for movement...
    print(f"\nAverage weight per kit: {avg_weight:.1f} kg")
    print(f"Total kits needed: {total_kits:,}")

if __name__ == "__main__":
    main()
