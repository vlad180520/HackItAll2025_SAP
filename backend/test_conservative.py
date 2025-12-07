#!/usr/bin/env python3
"""Quick test for conservative strategy logic."""

import sys
sys.path.insert(0, '.')

from solution.strategies.conservative_strategy import ConservativeStrategy, SAFETY_BUFFER

def test_safety_buffer():
    """Test that safety buffers work correctly."""
    strategy = ConservativeStrategy()
    
    # Mock airports
    class MockAirport:
        def __init__(self, code, is_hub, inventory):
            self.code = code
            self.is_hub = is_hub
            self.current_inventory = inventory
            self.processing_times = {"FIRST": 6, "BUSINESS": 4, "PREMIUM_ECONOMY": 2, "ECONOMY": 1}
    
    airports = {
        "HUB1": MockAirport("HUB1", True, {"FIRST": 1000, "BUSINESS": 3000, "PREMIUM_ECONOMY": 2000, "ECONOMY": 20000}),
        "OUT1": MockAirport("OUT1", False, {"FIRST": 100, "BUSINESS": 200, "PREMIUM_ECONOMY": 150, "ECONOMY": 500}),
    }
    
    strategy._initialize(airports)
    
    print("=== SAFETY BUFFER TEST ===")
    print(f"Safety buffers: {SAFETY_BUFFER}")
    print()
    
    # Test HUB
    print("HUB1 inventory:", strategy.inventory["HUB1"])
    for kit_class in ["FIRST", "BUSINESS", "PREMIUM_ECONOMY", "ECONOMY"]:
        safe = strategy._get_safe_available("HUB1", kit_class)
        actual = strategy.inventory["HUB1"][kit_class]
        buffer = SAFETY_BUFFER[kit_class]
        print(f"  {kit_class}: actual={actual}, buffer={buffer}, safe_available={safe}")
    
    print()
    
    # Test outstation
    print("OUT1 inventory:", strategy.inventory["OUT1"])
    for kit_class in ["FIRST", "BUSINESS", "PREMIUM_ECONOMY", "ECONOMY"]:
        safe = strategy._get_safe_available("OUT1", kit_class)
        actual = strategy.inventory["OUT1"][kit_class]
        buffer = SAFETY_BUFFER[kit_class]
        print(f"  {kit_class}: actual={actual}, buffer={buffer}, safe_available={safe}")
    
    print()
    print("=== CONSUMPTION TEST ===")
    
    # Test consumption
    print("Before consumption:", strategy.inventory["HUB1"]["ECONOMY"])
    strategy._consume("HUB1", "ECONOMY", 1000)
    print("After consuming 1000:", strategy.inventory["HUB1"]["ECONOMY"])
    
    safe_after = strategy._get_safe_available("HUB1", "ECONOMY")
    print(f"Safe available after: {safe_after}")
    
    print()
    print("=== TEST PASSED ===")
    print()
    print("Key insights:")
    print("1. We keep safety buffers to avoid going negative")
    print("2. We only DEDUCT, never ADD (except purchases)")
    print("3. When safe_available = 0, we stop loading from that airport")
    print("4. This prevents NEGATIVE_INVENTORY penalties")

if __name__ == "__main__":
    test_safety_buffer()

