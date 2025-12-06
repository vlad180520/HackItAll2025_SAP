"""
MATHEMATICAL PENALTY ANALYSIS - HackItAll 2025 SAP
===================================================

Based on analysis of eval-platform Java source code.

PENALTY FACTORS (from PenaltyFactors.java):
==========================================

1. FLIGHT_OVERLOAD_FACTOR_PER_DISTANCE = 5
   Penalty = 5 × kit_cost × distance × kits_over_capacity
   
   Examples for 500km flight:
   - First (cost=200): 5 × 200 × 500 × kits = 500,000 per kit!
   - Economy (cost=50): 5 × 50 × 500 × kits = 125,000 per kit!
   
   **CRITICAL**: Overload penalty is 500-2500× operational cost!
   **NEVER OVERLOAD AIRCRAFT!**

2. UNFULFILLED_KIT_FACTOR_PER_DISTANCE = 0.003
   Penalty = 0.003 × kit_cost × distance × missing_kits
   
   Examples for 500km flight:
   - First (cost=200): 0.003 × 200 × 500 = 300 per missing kit
   - Economy (cost=50): 0.003 × 50 × 500 = 75 per missing kit
   
   Break-even distance (when penalty = cost):
   - First: 333km (penalty = 200)
   - Business: 333km (penalty = 150)
   - Premium: 333km (penalty = 100)
   - Economy: 333km (penalty = 50)
   
   For distances > 333km: Unfulfilled penalty > kit cost
   **Use 1 kit buffer on longer flights!**

3. NEGATIVE_INVENTORY = 5342 per kit per round
   **This is MASSIVE! 26× First class kit cost!**
   **NEVER let inventory go negative!**

4. OVER_CAPACITY_STOCK = 777 per kit over capacity
   **Avoid overstocking beyond capacity!**

5. INCORRECT_FLIGHT_LOAD = 5000 (per flight)
6. EARLY_END_OF_GAME = 1000 (per missing hour)
7. END_OF_GAME_REMAINING_STOCK = 0.0013 × kit_cost × remaining
8. END_OF_GAME_PENDING_KIT_PROCESSING = 0.0013 × kit_cost × processing
9. END_OF_GAME_UNFULFILLED_FLIGHT_KITS = 1.5 × distance × missing

OPERATIONAL COSTS (from KitType.java):
====================================

Kit Purchase Costs:
- A_FIRST_CLASS: 200 (weight=5kg, lead_time=48h)
- B_BUSINESS: 150 (weight=3kg, lead_time=36h)
- C_PREMIUM_ECONOMY: 100 (weight=2.5kg, lead_time=24h)
- D_ECONOMY: 50 (weight=1.5kg, lead_time=12h)

Processing Times (from config.py):
- First: 6 hours
- Business: 4 hours
- Premium: 2 hours
- Economy: 1 hour

Movement Costs (from evaluation system):
- Loading cost: 0.5-3.3 per kit
- Processing cost: 1-8 per kit
- Fuel cost: fuel_price × distance × weight

OPTIMAL STRATEGY DERIVATION:
===========================

1. PRIORITY HIERARCHY:
   a) NEVER go negative inventory (-5342 penalty!)
   b) NEVER overload aircraft (500,000+ penalty!)
   c) Avoid unfulfilled passengers (300-1500 penalty on long flights)
   d) Minimize operational costs (50-200 per kit)

2. BUFFER CALCULATION:
   
   For short flights (< 333km):
   - Unfulfilled penalty < kit cost
   - HUB: 0 buffer (can restock instantly)
   - Outstations: 1 kit (safety, can't restock)
   
   For medium/long flights (≥ 333km, ~80% of flights):
   - Unfulfilled penalty ≥ kit cost
   - HUB: 1 kit buffer (penalty > cost)
   - Outstations: 1-2 kits (safety + penalty avoidance)
   
   **Most flights are 500-2000km → 1 kit buffer is CHEAPER than penalty!**

3. ACTUAL vs PLANNED PASSENGERS:
   
   flight.actual_passengers available 1h before departure (CHECKED_IN event)
   - Use actual when available (more accurate)
   - Use planned as fallback (schedule data)
   
   This eliminates waste from no-shows and overbooking adjustments.

4. PURCHASE TIMING:
   
   Lead times:
   - First: 48h → Purchase 48h+ in advance
   - Business: 36h → Purchase 36h+ in advance
   - Premium: 24h → Purchase 24h+ in advance
   - Economy: 12h → Purchase 12h+ in advance
   
   **Must account for processing time AFTER purchase!**
   - First needs: 48h delivery + 6h processing = 54h total
   - Economy needs: 12h delivery + 1h processing = 13h total

5. INVENTORY MANAGEMENT:
   
   Purchase when: current_stock + in_transit < forecast_demand + safety_margin
   
   Safety margin:
   - HUB: 5-10 kits (can restock quickly)
   - Outstations: 3-5 kits (can't restock, rely on returns)
   
   **CRITICAL**: Track kits in transit + processing to avoid double-purchasing!

6. LOADING STRATEGY:
   
   ```python
   if flight.distance >= 333:  # Long flight
       buffer = 1  # Penalty > cost
   else:  # Short flight
       buffer = 1 if is_outstation else 0  # Safety at outstations only
   
   kits_to_load = actual_passengers + buffer
   kits_to_load = min(kits_to_load, aircraft_capacity)  # NEVER overload!
   kits_to_load = min(kits_to_load, available_inventory)  # Can't load what we don't have
   ```

EXPECTED RESULTS:
================

Baseline (no optimization): ~$2M-3M total cost
Previous strategy (zero-waste): ~$800K-1M total cost
New strategy (penalty-aware): ~$400K-600K total cost

Cost Breakdown:
- Operational costs: $300K-400K (can't avoid, need kits for passengers)
- Buffer costs: $100K-150K (1 kit/flight × 7,287 flights × $50 avg)
- Movement costs: $50K-100K (loading + processing + fuel)
- Penalties: $0-50K (minimize to near-zero)

**Target: 60-80% reduction vs baseline, 30-50% vs zero-waste**

KEY INSIGHT: Zero-waste strategy was TOO aggressive!
- Saved $20-50 per kit on buffers
- But risked $300-1500 penalties per missing kit on long flights!
- Mathematical optimum: Accept buffer cost to avoid massive penalties

IMPLEMENTATION: Distance-Aware Dynamic Buffer Strategy
======================================================
"""

# Calculate exact break-even and penalty values
print("\n" + "="*70)
print("PENALTY vs COST ANALYSIS")
print("="*70)

for class_name, kit_cost, weight in [
    ("First", 200, 5.0),
    ("Business", 150, 3.0),
    ("Premium", 100, 2.5),
    ("Economy", 50, 1.5)
]:
    print(f"\n{class_name} Class (cost=${kit_cost}, weight={weight}kg):")
    print("-" * 60)
    
    # Unfulfilled penalty
    unfulfilled_factor = 0.003 * kit_cost
    breakeven_dist = kit_cost / unfulfilled_factor
    
    print(f"  Unfulfilled penalty factor: ${unfulfilled_factor:.2f}/km")
    print(f"  Break-even distance: {breakeven_dist:.0f}km")
    
    # Example penalties
    for distance in [100, 333, 500, 1000, 2000]:
        unfulfilled_penalty = unfulfilled_factor * distance
        overload_penalty = 5 * kit_cost * distance
        ratio_unfulfilled = unfulfilled_penalty / kit_cost
        ratio_overload = overload_penalty / kit_cost
        
        print(f"    @ {distance}km: unfulfilled=${unfulfilled_penalty:,.0f} ({ratio_unfulfilled:.1f}×cost), "
              f"overload=${overload_penalty:,} ({ratio_overload:.0f}×cost)")

print("\n" + "="*70)
print("STRATEGIC RECOMMENDATIONS")
print("="*70)
print("""
1. ALWAYS load EXACT actual_passengers (when available)
2. Add 1 kit buffer for flights ≥ 333km (80% of flights)
3. Add 0 kit buffer for HUB short flights < 333km
4. Add 1 kit buffer for outstation flights (can't restock)
5. Purchase 54h ahead for First, 13h ahead for Economy
6. Track in-transit kits to avoid double-purchasing
7. Maintain 5-10 kit safety stock at HUB
8. NEVER overload (500-2500× cost penalty!)
9. NEVER go negative inventory (5342 penalty!)
10. Accept small buffer cost to avoid massive unfulfilled penalties
""")

print("\nEXPECTED IMPACT:")
print("  - Operational costs: $300K-400K (unavoidable)")
print("  - Buffer costs: $100K-150K (1 kit × 7,287 × $50)")
print("  - Penalties: $0-50K (minimized)")
print("  - TOTAL: $400K-600K (60-70% reduction vs baseline)")
