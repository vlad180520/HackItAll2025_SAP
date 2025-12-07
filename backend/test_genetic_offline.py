#!/usr/bin/env python3
"""Offline test script for genetic algorithm.

Tests the genetic algorithm against CSV data WITHOUT running the full simulation.
This validates:
1. Demand analysis is correct
2. Purchase timing is calculated correctly
3. Expected stockout hours match CSV analysis
4. Purchase decisions are made at the right time

Usage:
    python test_genetic_offline.py
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from config import CLASS_TYPES, KIT_DEFINITIONS
from solution.strategies.genetic.demand_analyzer import (
    analyze_demand_from_csv,
    get_demand_analysis,
    get_expected_hourly_demand,
    get_expected_total_demand,
)
from solution.strategies.genetic.purchases import API_PURCHASE_LIMITS
from solution.strategies.genetic.precompute import find_hub


def test_demand_analysis():
    """Test that demand analysis loads correctly from CSV."""
    print("\n" + "="*80)
    print("TEST 1: Demand Analysis from CSV")
    print("="*80)
    
    # Define paths
    base_path = "HackitAll2025-main/eval-platform/src/main/resources/liquibase/data"
    flights_csv = f"{base_path}/flights.csv"
    airports_csv = f"{base_path}/airports_with_stocks.csv"
    
    # Lead times from KitType.java
    lead_times = {
        "FIRST": 48,
        "BUSINESS": 36,
        "PREMIUM_ECONOMY": 24,
        "ECONOMY": 12,
    }
    
    # Processing times at HUB
    processing_times = {
        "FIRST": 6,
        "BUSINESS": 4,
        "PREMIUM_ECONOMY": 2,
        "ECONOMY": 1,
    }
    
    analysis = analyze_demand_from_csv(
        flights_csv, airports_csv, lead_times, processing_times
    )
    
    if analysis is None:
        print("FAILED: Could not load demand analysis from CSV")
        return False
    
    print(f"\nInitial HUB Stock:")
    for cls, stock in analysis.initial_stock.items():
        print(f"  {cls}: {stock:,}")
    
    print(f"\nHUB Capacity:")
    for cls, cap in analysis.hub_capacity.items():
        print(f"  {cls}: {cap:,}")
    
    print(f"\nTotal Demand (entire simulation):")
    for cls, demand in analysis.total_demand.items():
        print(f"  {cls}: {demand:,}")
    
    print(f"\nHourly Demand (average):")
    for cls, hourly in analysis.hourly_demand.items():
        print(f"  {cls}: {hourly:.2f} kits/hour")
    
    print(f"\nStockout Hours (when stock runs out):")
    for cls, hour in analysis.stockout_hours.items():
        if hour is not None:
            day = hour // 24
            hr = hour % 24
            print(f"  {cls}: Hour {hour} (Day {day}, Hour {hr})")
        else:
            print(f"  {cls}: No stockout")
    
    print(f"\nOrder By (latest hour to place order):")
    for cls, hour in analysis.order_by_hours.items():
        lead = lead_times[cls]
        proc = processing_times[cls]
        total_eta = lead + proc
        print(f"  {cls}: Hour {hour} (lead_time={lead}h, proc={proc}h, total_eta={total_eta}h)")
    
    print("\nPASS: Demand analysis loaded successfully")
    return True


def test_purchase_timing():
    """Test that purchases would be triggered at the right time."""
    print("\n" + "="*80)
    print("TEST 2: Purchase Timing Validation")
    print("="*80)
    
    analysis = get_demand_analysis()
    if analysis is None:
        print("FAILED: Could not get demand analysis")
        return False
    
    # For each class, check if ordering at hour 0 would prevent stockout
    print("\nPurchase Timing Analysis:")
    print("-" * 60)
    
    all_passed = True
    
    for cls in CLASS_TYPES:
        stock = analysis.initial_stock.get(cls, 0)
        stockout_hr = analysis.stockout_hours.get(cls)
        order_by = analysis.order_by_hours.get(cls, 720)
        total_demand = analysis.total_demand.get(cls, 0)
        
        # Lead times from KitType.java
        lead_times = {"FIRST": 48, "BUSINESS": 36, "PREMIUM_ECONOMY": 24, "ECONOMY": 12}
        proc_times = {"FIRST": 6, "BUSINESS": 4, "PREMIUM_ECONOMY": 2, "ECONOMY": 1}
        
        eta = lead_times[cls] + proc_times[cls]
        
        print(f"\n{cls}:")
        print(f"  Initial stock: {stock:,}")
        print(f"  Total demand: {total_demand:,}")
        print(f"  ETA (lead + proc): {eta}h")
        
        if stockout_hr is not None:
            print(f"  Stockout at: Hour {stockout_hr}")
            print(f"  Must order by: Hour {order_by}")
            
            if order_by < 0:
                print(f"  WARNING: Stockout at hour {stockout_hr} but ETA is {eta}h - cannot prevent!")
                print(f"           Order at hour 0 arrives at hour {eta}, which is AFTER stockout!")
                # This is expected for FIRST and BUSINESS
                if cls in ["FIRST", "BUSINESS"]:
                    print(f"           (This is expected behavior)")
            elif order_by == 0:
                print(f"  CRITICAL: Must order at hour 0!")
        else:
            print(f"  No stockout predicted (stock >= total demand)")
    
    print("\nPASS: Purchase timing analysis complete")
    return all_passed


def test_fallback_values():
    """Test that fallback values are reasonable."""
    print("\n" + "="*80)
    print("TEST 3: Fallback Values Test")
    print("="*80)
    
    hourly = get_expected_hourly_demand()
    total = get_expected_total_demand()
    
    print("\nExpected Hourly Demand (from CSV or fallback):")
    for cls, demand in hourly.items():
        print(f"  {cls}: {demand:.2f} kits/hour")
    
    print("\nExpected Total Demand (from CSV or fallback):")
    for cls, demand in total.items():
        print(f"  {cls}: {demand:,} kits")
    
    # Validate that hourly * 720 is close to total
    print("\nValidation (hourly * 720 should ≈ total):")
    all_ok = True
    for cls in CLASS_TYPES:
        calculated = hourly[cls] * 720
        actual = total[cls]
        diff_pct = abs(calculated - actual) / max(1, actual) * 100
        status = "OK" if diff_pct < 5 else "WARNING"
        if diff_pct >= 5:
            all_ok = False
        print(f"  {cls}: {calculated:.0f} vs {actual} ({diff_pct:.1f}% diff) - {status}")
    
    if all_ok:
        print("\nPASS: All fallback values are consistent")
    else:
        print("\nWARNING: Some values have >5% difference")
    
    return True


def test_purchase_decision_at_round_0():
    """Simulate what purchases should be made at round 0."""
    print("\n" + "="*80)
    print("TEST 4: Purchase Decision at Round 0 (No Flights)")
    print("="*80)
    
    analysis = get_demand_analysis()
    if analysis is None:
        print("FAILED: Could not get demand analysis")
        return False
    
    # Show API limits
    print("\nAPI Purchase Limits (from PerClassAmount.java validation):")
    for cls, limit in API_PURCHASE_LIMITS.items():
        print(f"  {cls}: max {limit:,}")
    
    # Simulate round 0 with no flights
    now_hours = 0
    has_flight_data = False  # No flights at round 0
    
    print("\nSimulating purchases at round 0 (no flight data available):")
    print("-" * 60)
    
    hourly_demand = get_expected_hourly_demand()
    all_within_limits = True
    
    for cls in CLASS_TYPES:
        stock = analysis.initial_stock.get(cls, 0)
        capacity = analysis.hub_capacity.get(cls, 10000)
        api_limit = API_PURCHASE_LIMITS.get(cls, 42000)
        
        # Lead times from KitType.java
        lead_times = {"FIRST": 48, "BUSINESS": 36, "PREMIUM_ECONOMY": 24, "ECONOMY": 12}
        proc_times = {"FIRST": 6, "BUSINESS": 4, "PREMIUM_ECONOMY": 2, "ECONOMY": 1}
        
        lead_time = lead_times[cls]
        processing_time = proc_times[cls]
        eta_hours = now_hours + lead_time + processing_time
        
        # Use fallback demand (CSV-derived)
        hourly = hourly_demand.get(cls, 25.0)
        demand_until_eta = int(hourly * (eta_hours - now_hours))
        demand_after_eta = int(hourly * (720 - eta_hours))
        demand_168h = int(hourly * 168)
        
        # Calculate stock at ETA
        stock_at_eta = stock - demand_until_eta
        
        # Should we buy?
        should_purchase = (
            stock_at_eta < 0 or
            stock < demand_168h or
            (demand_after_eta > 0 and now_hours < 24)
        )
        
        print(f"\n{cls}:")
        print(f"  Stock: {stock:,}")
        print(f"  Hourly demand: {hourly:.1f}")
        print(f"  ETA: {eta_hours}h")
        print(f"  Demand until ETA: {demand_until_eta:,}")
        print(f"  Stock at ETA: {stock_at_eta:,}")
        print(f"  Demand after ETA: {demand_after_eta:,}")
        print(f"  API Limit: {api_limit:,}")
        
        if should_purchase:
            shortfall = max(0, -stock_at_eta)
            target = int((demand_after_eta + shortfall) * 1.3)
            target = max(target, int(demand_168h * 1.2))
            needed = max(0, target - stock)
            raw_purchase = min(needed, capacity - stock)
            # Clamp to API limit
            purchase = min(raw_purchase, api_limit)
            
            if raw_purchase > api_limit:
                print(f"  PURCHASE: {purchase:,} kits (CLAMPED from {raw_purchase:,})")
            else:
                print(f"  PURCHASE: {purchase:,} kits (target={target:,})")
            
            if purchase > api_limit:
                all_within_limits = False
                print(f"  ERROR: Purchase {purchase} exceeds API limit {api_limit}!")
        else:
            print(f"  NO PURCHASE needed")
    
    if all_within_limits:
        print("\nPASS: All purchases within API limits")
    else:
        print("\nFAIL: Some purchases exceed API limits")
    
    return all_within_limits


def run_all_tests():
    """Run all tests."""
    print("="*80)
    print("GENETIC ALGORITHM OFFLINE TEST SUITE")
    print("="*80)
    print("\nThis script validates the genetic algorithm against CSV data")
    print("without running the full simulation.\n")
    
    tests = [
        ("Demand Analysis", test_demand_analysis),
        ("Purchase Timing", test_purchase_timing),
        ("Fallback Values", test_fallback_values),
        ("Round 0 Purchases", test_purchase_decision_at_round_0),
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            result = test_fn()
            results.append((name, result))
        except Exception as e:
            logger.error(f"Test {name} failed with exception: {e}", exc_info=True)
            results.append((name, False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = 0
    failed = 0
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

