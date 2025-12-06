"""Service for simulation management."""

import logging
from typing import Dict, Optional
from config import Config
from api_client import ValidationError
from data_loader import load_airports, load_aircraft_types, load_flight_schedule
from api_client import ExternalAPIClient
from state_manager import StateManager
from solution.decision_maker import DecisionMaker
from validator import Validator
from simulation_runner import SimulationRunner
from models.game_state import GameState
from config import KIT_DEFINITIONS, AIRPORTS_CSV, AIRCRAFT_TYPES_CSV, FLIGHT_PLAN_CSV
from utils import format_cost

logger = logging.getLogger(__name__)


class SimulationService:
    """Service for managing simulation state and operations."""
    
    def __init__(self):
        """Initialize simulation service."""
        self.config = Config()
        self.simulation_state: Optional[Dict] = None
        self.simulation_runner: Optional[SimulationRunner] = None
        self.current_session_id: Optional[str] = None
    
    def initialize_simulation(self) -> SimulationRunner:
        """
        Initialize simulation components.
        
        Returns:
            Initialized SimulationRunner
        """
        # Load data
        airports = load_airports(AIRPORTS_CSV, self.config)
        aircraft = load_aircraft_types(AIRCRAFT_TYPES_CSV)
        # Note: Flights are provided by the evaluation platform via API responses,
        # not loaded from CSV. The flight_plan.csv is just a schedule template.
        
        # Initialize initial game state
        initial_inventories = {}
        for code, airport in airports.items():
            initial_inventories[code] = airport.current_inventory
        
        initial_state = GameState(
            current_day=0,
            current_hour=0,  # Evaluation platform starts at day 0, hour 0
            airport_inventories=initial_inventories,
            in_process_kits={},
            pending_movements=[],
            total_cost=0.0,
            penalty_log=[],
            flight_history=[],
        )
        
        # Initialize components
        api_client = ExternalAPIClient(
            base_url=self.config.API_BASE_URL,
            api_key_header=self.config.API_KEY_HEADER,
        )
        state_manager = StateManager(initial_state)
        optimizer = DecisionMaker(self.config)
        validator = Validator(airports, aircraft, KIT_DEFINITIONS)
        
        runner = SimulationRunner(
            api_client=api_client,
            state_manager=state_manager,
            optimizer=optimizer,
            validator=validator,
            airports=airports,
            aircraft=aircraft,
            kit_defs=KIT_DEFINITIONS,
            config=self.config,
        )
        
        return runner
    
    def get_status(self) -> Dict:
        """
        Get current simulation status.
        
        Returns:
            Status dictionary with formatted costs
        """
        # If simulation is running, get live data from runner
        if self.simulation_runner is not None:
            state = self.simulation_runner.state_manager.current_state
            # Count rounds from decision log
            rounds = len(self.simulation_runner.decision_log)
            return {
                "status": "running",
                "round": rounds,
                "costs": state.total_cost,  # Numeric value
                "costs_formatted": format_cost(state.total_cost),  # Formatted string
                "penalties": [p.dict() for p in state.penalty_log[-10:]],  # Last 10 penalties
            }
        
        # If simulation completed, get from final report
        if self.simulation_state is not None:
            penalty_log = self.simulation_state.get("penalty_log", [])
            # Convert PenaltyRecord objects to dicts if needed
            if penalty_log and hasattr(penalty_log[0], 'dict'):
                penalty_log = [p.dict() for p in penalty_log]
            elif penalty_log and isinstance(penalty_log[0], dict):
                pass  # Already dicts
            else:
                penalty_log = []
            
            total_cost = self.simulation_state.get("total_cost", 0.0)
            return {
                "status": "completed",
                "round": self.simulation_state.get("rounds_completed", 0),
                "costs": total_cost,  # Numeric value
                "costs_formatted": format_cost(total_cost),  # Formatted string
                "penalties": penalty_log[-10:],  # Last 10 penalties
            }
        
        # No simulation started
        return {
            "status": "not_started",
            "round": 0,
            "costs": 0.0,
            "costs_formatted": "0,00",
            "penalties": [],
        }
    
    def get_inventory(self) -> Dict:
        """
        Get current airport inventories.
        
        Returns:
            Inventory dictionary
        """
        # If simulation is running, get live data from runner
        if self.simulation_runner is not None:
            state = self.simulation_runner.state_manager.current_state
            return {"inventories": state.airport_inventories}
        
        # If simulation completed, get from final state
        if self.simulation_state is not None:
            final_state = self.simulation_state.get("final_state", {})
            inventories = final_state.get("airport_inventories", {})
            return {"inventories": inventories}
        
        # No simulation started
        return {"inventories": {}}
    
    def get_history(self, limit: Optional[int] = 20) -> Dict:
        """
        Get decision and cost history.
        
        Args:
            limit: Number of recent entries to return (None for all)
        
        Returns:
            History dictionary with decision_log and cost_log
        """
        if self.simulation_runner is None:
            return {"decision_log": [], "cost_log": [], "total_rounds": 0}
        
        decision_log = self.simulation_runner.decision_log
        cost_log = self.simulation_runner.cost_log
        
        # Apply limit if specified
        if limit is not None:
            decision_log = decision_log[-limit:]
            cost_log = cost_log[-limit:]
        
        return {
            "decision_log": decision_log,
            "cost_log": cost_log,
            "total_rounds": len(self.simulation_runner.decision_log),
        }
    
    def start_simulation(self, api_key: str, stop_existing: bool = True) -> None:
        """
        Start simulation (sets up runner, actual execution happens in background task).
        
        Args:
            api_key: API key for authentication
            stop_existing: If True, stop any existing session on evaluation platform first
        """
        if self.simulation_runner is not None:
            raise ValueError("Simulation already running")
        
        self.simulation_runner = self.initialize_simulation()
        # Store API key and settings for potential cleanup
        self.current_api_key = api_key
        self.stop_existing = stop_existing
        logger.info("Simulation runner initialized")
    
    def run_simulation_task(self, api_key: str) -> None:
        """
        Background task to run simulation.
        
        Args:
            api_key: API key for authentication
        """
        try:
            logger.info("Starting simulation task")
            
            # Initialize simulation state
            self.simulation_state = {
                "status": "running",
                "rounds_completed": 0,
                "total_cost": 0.0,
                "penalty_log": [],
            }
            
            # Pass stop_existing flag and update callback to runner
            def update_progress(round_num: int, total_cost: float, penalties: list):
                """Callback to update state during simulation."""
                logger.info(f"Progress update: Round {round_num}, Cost {total_cost:.2f}")
                if self.simulation_state:
                    self.simulation_state["rounds_completed"] = round_num
                    self.simulation_state["total_cost"] = total_cost
                    self.simulation_state["penalty_log"] = penalties[-10:]  # Keep last 10
                    logger.debug(f"State updated: {self.simulation_state['rounds_completed']} rounds, ${self.simulation_state['total_cost']:.2f}")
            
            final_report = self.simulation_runner.run(
                api_key=api_key, 
                stop_existing=self.stop_existing,
                progress_callback=update_progress
            )
            # Store session_id from final report
            if 'session_id' in final_report:
                self.current_session_id = final_report['session_id']
            self.simulation_state = final_report
            logger.info("Simulation task completed")
        except Exception as e:
            logger.error(f"Error in simulation task: {e}")
            self.simulation_state = {"error": str(e), "status": "error"}
        finally:
            # Clear runner after completion
            self.simulation_runner = None
            self.current_api_key = None
            self.current_session_id = None
    
    def stop_simulation(self) -> Dict:
        """
        Stop the current simulation and end the session on evaluation platform.
        
        Returns:
            Final session report
        """
        if self.simulation_runner is None:
            raise ValueError("No simulation running")
        
        if not hasattr(self, 'current_api_key') or self.current_api_key is None:
            raise ValueError("No API key available for stopping session")
        
        try:
            # Stop session on evaluation platform
            api_client = self.simulation_runner.api_client
            session_id = getattr(self, 'current_session_id', None)
            final_report = api_client.stop_session(self.current_api_key, session_id=session_id)
            
            # Clear state
            self.simulation_runner = None
            self.current_api_key = None
            self.current_session_id = None
            
            return final_report
        except Exception as e:
            logger.error(f"Error stopping simulation: {e}")
            raise

