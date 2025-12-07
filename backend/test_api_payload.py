"""
Test what payload gets sent to the API.
Mock the API call to capture the actual payload.
"""
import sys
sys.path.insert(0, '.')

# Mock the api_client before importing simulation_runner
import json

class MockAPIClient:
    def __init__(self):
        self.payloads = []
        self.session_id = "test-session"
        
    def start_session(self, api_key, stop_existing=True):
        print("MockAPI: start_session called")
        return self.session_id
    
    def stop_session(self, api_key, session_id=None):
        print("MockAPI: stop_session called")
        return {"status": "stopped"}
    
    def play_round(self, api_key, session_id, day, hour, flight_loads, kit_purchasing_orders):
        payload = {
            "day": day,
            "hour": hour,
            "flight_loads": flight_loads,
            "kit_purchasing_orders": kit_purchasing_orders,
        }
        self.payloads.append(payload)
        
        # Print what we're sending
        total_loads = len(flight_loads)
        total_purchases = sum(kit_purchasing_orders.values())
        print(f"MockAPI play_round: day={day}, hour={hour}, loads={total_loads}, purchases={total_purchases}")
        
        if total_loads > 0:
            print(f"  BUG! Flight loads should be 0: {flight_loads}")
        if total_purchases > 0:
            print(f"  BUG! Purchases should be 0: {kit_purchasing_orders}")
        
        # Return mock response
        return {
            "day": day,
            "hour": hour + 1 if hour < 23 else 0,
            "totalCost": 0.0,
            "penalties": [],
            "flightUpdates": [],
        }

# Test the flow
from state_manager import StateManager
from validator import Validator
from models.game_state import GameState
from models.airport import Airport
from models.aircraft import AircraftType
from solution.decision_maker import DecisionMaker
from config import Config

def test_api_payload():
    print("Setting up test...")
    
    # Create initial state
    state = GameState(
        current_day=0,
        current_hour=0,
        airport_inventories={"HUB1": {"FIRST": 1000, "BUSINESS": 5000}},
        pending_movements=[],
        flight_history=[],
        total_cost=0.0,
        in_process_kits={},
        penalty_log=[],
    )
    
    airports = {
        "HUB1": Airport(
            code="HUB1",
            name="Hub",
            is_hub=True,
            processing_times={"FIRST": 6, "BUSINESS": 4},
            processing_costs={"FIRST": 8, "BUSINESS": 6},
            loading_costs={"FIRST": 1, "BUSINESS": 0.75},
            current_inventory={"FIRST": 1000, "BUSINESS": 5000},
            storage_capacity={"FIRST": 18000, "BUSINESS": 18000},
        )
    }
    
    aircraft = {
        "A320": AircraftType(
            type_code="A320",
            fuel_cost_per_km=0.5,
            kit_capacity={"FIRST": 10, "BUSINESS": 30},
            passenger_capacity={"FIRST": 10, "BUSINESS": 30},
        )
    }
    
    kit_defs = {}
    config = Config()
    
    # Create components
    mock_api = MockAPIClient()
    state_manager = StateManager(state)
    optimizer = DecisionMaker()
    validator = Validator(airports, aircraft, kit_defs)
    
    # Import SimulationRunner after setup
    from simulation_runner import SimulationRunner
    
    runner = SimulationRunner(
        api_client=mock_api,
        state_manager=state_manager,
        optimizer=optimizer,
        validator=validator,
        airports=airports,
        aircraft=aircraft,
        kit_defs=kit_defs,
        config=config,
    )
    
    print("\nRunning 10 rounds with mock API...")
    
    try:
        result = runner.run(api_key="test-key", max_rounds=10, stop_existing=False)
    except Exception as e:
        print(f"Error: {e}")
        # Even if there's an error, check payloads
    
    print(f"\n--- API Payloads Summary ---")
    print(f"Total API calls: {len(mock_api.payloads)}")
    
    all_zero = True
    for i, p in enumerate(mock_api.payloads):
        loads = len(p['flight_loads'])
        purchases = sum(p['kit_purchasing_orders'].values())
        if loads != 0 or purchases != 0:
            print(f"Round {i}: loads={loads}, purchases={purchases} - NOT ZERO!")
            all_zero = False
    
    if all_zero:
        print("✓ All API calls had ZERO loads and ZERO purchases!")
        return True
    else:
        print("FAIL: Some rounds had non-zero loads or purchases")
        return False

if __name__ == "__main__":
    success = test_api_payload()
    sys.exit(0 if success else 1)
