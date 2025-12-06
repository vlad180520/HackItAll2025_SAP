"""
Test script to demonstrate genetic algorithm strategy.

This script creates a minimal test scenario and runs the genetic algorithm
to show how it optimizes kit loading decisions.
"""

import logging
from solution.strategies.genetic_strategy import GeneticStrategy, GeneticConfig
from solution.config import SolutionConfig
from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.airport import Airport
from models.aircraft import AircraftType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def create_test_scenario():
    """Create a simple test scenario with one hub and one outstation."""
    
    # Create airports
    hub = Airport(
        code="HUB1",
        name="Main Hub",
        is_hub=True,
        storage_capacity={"FIRST": 100, "BUSINESS": 150, "PREMIUM_ECONOMY": 200, "ECONOMY": 300},
        loading_costs={"FIRST": 10.0, "BUSINESS": 8.0, "PREMIUM_ECONOMY": 6.0, "ECONOMY": 5.0},
        processing_costs={"FIRST": 5.0, "BUSINESS": 4.0, "PREMIUM_ECONOMY": 3.0, "ECONOMY": 2.0},
        processing_times={"FIRST": 6, "BUSINESS": 4, "PREMIUM_ECONOMY": 2, "ECONOMY": 1},
        current_inventory={"FIRST": 50, "BUSINESS": 80, "PREMIUM_ECONOMY": 100, "ECONOMY": 150}
    )
    
    outstation = Airport(
        code="OUT1",
        name="Outstation 1",
        is_hub=False,
        storage_capacity={"FIRST": 50, "BUSINESS": 75, "PREMIUM_ECONOMY": 100, "ECONOMY": 150},
        loading_costs={"FIRST": 12.0, "BUSINESS": 10.0, "PREMIUM_ECONOMY": 8.0, "ECONOMY": 6.0},
        processing_costs={"FIRST": 8.0, "BUSINESS": 6.0, "PREMIUM_ECONOMY": 4.0, "ECONOMY": 3.0},
        processing_times={"FIRST": 45, "BUSINESS": 30, "PREMIUM_ECONOMY": 20, "ECONOMY": 10},
        current_inventory={"FIRST": 20, "BUSINESS": 30, "PREMIUM_ECONOMY": 40, "ECONOMY": 60}
    )
    
    airports = {"HUB1": hub, "OUT1": outstation}
    
    # Create aircraft type
    aircraft = AircraftType(
        type_code="A320",
        passenger_capacity={"FIRST": 10, "BUSINESS": 30, "PREMIUM_ECONOMY": 40, "ECONOMY": 100},
        kit_capacity={"FIRST": 10, "BUSINESS": 30, "PREMIUM_ECONOMY": 40, "ECONOMY": 100},
        fuel_cost_per_km=0.5
    )
    
    aircraft_types = {"A320": aircraft}
    
    # Create flights (departing in current hour and next hour)
    flights = [
        Flight(
            flight_id="FL001",
            flight_number="AA100",
            origin="HUB1",
            destination="OUT1",
            scheduled_departure=ReferenceHour(day=1, hour=10),
            scheduled_arrival=ReferenceHour(day=1, hour=14),
            planned_passengers={"FIRST": 8, "BUSINESS": 25, "PREMIUM_ECONOMY": 35, "ECONOMY": 90},
            planned_distance=2000.0,
            aircraft_type="A320",
            event_type="SCHEDULED"
        ),
        Flight(
            flight_id="FL002",
            flight_number="AA101",
            origin="OUT1",
            destination="HUB1",
            scheduled_departure=ReferenceHour(day=1, hour=11),
            scheduled_arrival=ReferenceHour(day=1, hour=15),
            planned_passengers={"FIRST": 5, "BUSINESS": 20, "PREMIUM_ECONOMY": 30, "ECONOMY": 80},
            planned_distance=2000.0,
            aircraft_type="A320",
            event_type="SCHEDULED"
        )
    ]
    
    # Create game state
    state = GameState(
        current_day=1,
        current_hour=10,
        airport_inventories={
            "HUB1": hub.current_inventory.copy(),
            "OUT1": outstation.current_inventory.copy()
        },
        in_process_kits={},
        pending_movements=[],
        total_cost=0.0,
        penalty_log=[],
        flight_history=[],
        cumulative_decisions=0,
        cumulative_purchases=0
    )
    
    return state, flights, airports, aircraft_types


def main():
    """Run the genetic algorithm test."""
    logger.info("=== Genetic Algorithm Strategy Test ===")
    
    # Create test scenario
    state, flights, airports, aircraft_types = create_test_scenario()
    
    logger.info("\n--- Test Scenario ---")
    logger.info(f"Current time: Day {state.current_day}, Hour {state.current_hour}")
    logger.info(f"Number of flights: {len(flights)}")
    logger.info(f"HUB1 inventory: {state.airport_inventories['HUB1']}")
    logger.info(f"OUT1 inventory: {state.airport_inventories['OUT1']}")
    
    # Create genetic strategy with custom config
    config = SolutionConfig.default()
    ga_config = GeneticConfig(
        population_size=20,
        num_generations=15,
        tournament_size=3,
        crossover_rate=0.8,
        mutation_rate=0.15,
        elitism_count=2,
        horizon_hours=2,
        no_improvement_limit=5
    )
    
    strategy = GeneticStrategy(config=config, ga_config=ga_config)
    
    logger.info("\n--- Running Genetic Algorithm ---")
    logger.info(f"Population size: {ga_config.population_size}")
    logger.info(f"Generations: {ga_config.num_generations}")
    logger.info(f"Horizon: {ga_config.horizon_hours} hours")
    
    # Run optimization
    load_decisions, purchase_orders = strategy.optimize(
        state=state,
        flights=flights,
        airports=airports,
        aircraft_types=aircraft_types
    )
    
    logger.info("\n--- Results ---")
    logger.info(f"Load decisions: {len(load_decisions)}")
    for decision in load_decisions:
        total_kits = sum(decision.kits_per_class.values())
        logger.info(f"  Flight {decision.flight_id}: {total_kits} total kits")
        for class_type, qty in decision.kits_per_class.items():
            if qty > 0:
                logger.info(f"    {class_type}: {qty}")
    
    logger.info(f"\nPurchase orders: {len(purchase_orders)}")
    for order in purchase_orders:
        total_purchase = sum(order.kits_per_class.values())
        logger.info(f"  Total purchase: {total_purchase} kits")
        for class_type, qty in order.kits_per_class.items():
            if qty > 0:
                logger.info(f"    {class_type}: {qty}")
    
    logger.info("\n=== Test Complete ===")


if __name__ == "__main__":
    main()
