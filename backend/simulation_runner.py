"""Simulation runner for orchestrating the 720-round simulation loop."""

import logging
from typing import Dict, List, Optional
from .api_client import ExternalAPIClient, ValidationError
from .state_manager import StateManager
from .optimizer import GreedyOptimizer
from .validator import Validator
from .cost_calculator import calculate_round_costs
from .models.game_state import GameState
from .models.flight import Flight, ReferenceHour
from .models.airport import Airport
from .models.aircraft import AircraftType
from .models.kit import KitLoadDecision, KitPurchaseOrder
from .models.game_state import PenaltyRecord
from .config import Config, TOTAL_ROUNDS

logger = logging.getLogger(__name__)


class SimulationRunner:
    """Orchestrates the simulation loop."""
    
    def __init__(
        self,
        api_client: ExternalAPIClient,
        state_manager: StateManager,
        optimizer: GreedyOptimizer,
        validator: Validator,
        airports: Dict[str, Airport],
        aircraft: Dict[str, AircraftType],
        kit_defs: Dict,
        config: Config,
    ):
        """
        Initialize simulation runner.
        
        Args:
            api_client: External API client
            state_manager: State manager
            optimizer: Optimizer instance
            validator: Validator instance
            airports: Dictionary of airports
            aircraft: Dictionary of aircraft types
            kit_defs: Kit definitions
            config: Configuration object
        """
        self.api_client = api_client
        self.state_manager = state_manager
        self.optimizer = optimizer
        self.validator = validator
        self.airports = airports
        self.aircraft = aircraft
        self.kit_defs = kit_defs
        self.config = config
        self.decision_log = []
        self.cost_log = []
    
    def run(self, api_key: str, max_rounds: int = TOTAL_ROUNDS, stop_existing: bool = True) -> Dict:
        """
        Run the main simulation loop.
        
        Args:
            api_key: API key for authentication
            max_rounds: Maximum number of rounds to run
            stop_existing: If True, stop any existing session first (default: True)
            
        Returns:
            Final report dictionary
        """
        logger.info(f"Starting simulation with max_rounds={max_rounds}")
        
        # Start session
        try:
            session_id = self.api_client.start_session(api_key, stop_existing=stop_existing)
            if not session_id:
                raise ValueError("No session_id returned from start_session")
            logger.info(f"Session started: {session_id}")
        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            raise
        
        round_num = 0
        # Track cumulative total cost from API (it's already cumulative)
        cumulative_total_cost = 0.0
        
        try:
            while round_num < max_rounds:
                # Get current time
                current_time = self.state_manager.state.get_current_time()
                
                # Get visible flights for current hour
                visible_flights = self._get_visible_flights(current_time)
                
                # Optimizer produces decisions
                decisions, purchases, rationale = self.optimizer.decide(
                    self.state_manager.state,
                    visible_flights,
                    self.airports,
                    self.aircraft,
                )
                
                # Validate decisions
                validation_report = self.validator.validate_decisions(
                    decisions, purchases, self.state_manager.state, visible_flights
                )
                
                if not validation_report.is_valid():
                    logger.error(f"Validation errors in round {round_num}: {validation_report.errors}")
                    # Stop on fatal errors
                    break
                
                if validation_report.warnings:
                    logger.warning(f"Validation warnings in round {round_num}: {validation_report.warnings}")
                
                # Calculate estimated costs
                cost_breakdown = calculate_round_costs(
                    self.state_manager.state,
                    decisions,
                    purchases,
                    self.airports,
                    self.aircraft,
                    visible_flights,
                )
                
                # Prepare API payload - aggregate purchases into single PerClassAmount
                total_purchases = {"FIRST": 0, "BUSINESS": 0, "PREMIUM_ECONOMY": 0, "ECONOMY": 0}
                for purchase in purchases:
                    for class_type, quantity in purchase.kits_per_class.items():
                        total_purchases[class_type] = total_purchases.get(class_type, 0) + quantity
                
                # Convert decisions to API format
                flight_loads = [d.dict() for d in decisions]
                
                # Submit round to API
                try:
                    response = self.api_client.play_round(
                        api_key=api_key,
                        session_id=session_id,
                        day=current_time.day,
                        hour=current_time.hour,
                        flight_loads=flight_loads,
                        kit_purchasing_orders=total_purchases,
                    )
                    
                    # Update state with response (this updates time to match API)
                    self._update_state_from_response(response, current_time)
                    
                    # Get updated time from response
                    response_day = response.get("day", current_time.day)
                    response_hour = response.get("hour", current_time.hour)
                    
                    # Log round
                    self.decision_log.append({
                        "round": round_num,
                        "time": {"day": response_day, "hour": response_hour},
                        "decisions": len(decisions),
                        "purchases": len(purchases),
                        "rationale": rationale,
                    })
                    
                    # API returns cumulative totalCost (running total), not incremental
                    api_total_cost = response.get("totalCost", 0.0)
                    cumulative_total_cost = api_total_cost  # Update cumulative total
                    
                    # Calculate incremental cost for this round (for logging)
                    # Get previous total from state or cost_log
                    previous_total = self.state_manager.state.total_cost if round_num == 0 else self.cost_log[-1].get("api_total_cost", 0.0) if self.cost_log else 0.0
                    incremental_cost = api_total_cost - previous_total
                    
                    self.cost_log.append({
                        "round": round_num,
                        "costs": cost_breakdown,
                        "penalties": response.get("penalties", []),
                        "api_total_cost": api_total_cost,
                        "incremental_cost": incremental_cost,
                    })
                    
                    # Update state's total cost with API's cumulative total
                    self.state_manager.state.total_cost = api_total_cost
                    
                    # Calculate next time for next round (API advances time after processing)
                    next_hour = response_hour + 1
                    next_day = response_day
                    if next_hour >= 24:
                        next_hour = 0
                        next_day += 1
                    
                    # Advance state to next hour for next round
                    self.state_manager.advance_time_to(next_day, next_hour, self.airports)
                    round_num += 1
                    
                except ValidationError as e:
                    logger.error(f"API validation error in round {round_num}: {e}")
                    break
                except Exception as e:
                    logger.error(f"Error in round {round_num}: {e}")
                    self.handle_errors(e)
                    break
                
                if round_num % 100 == 0:
                    logger.info(f"Completed {round_num} rounds, total cost: {cumulative_total_cost:.2f}")
        
        finally:
            # Stop session
            try:
                final_report = self.api_client.stop_session(api_key)
                logger.info("Session stopped")
            except Exception as e:
                logger.error(f"Error stopping session: {e}")
                final_report = {}
        
        # Generate final report
        final_report = {
            "rounds_completed": round_num,
            "total_cost": cumulative_total_cost,
            "final_state": self.state_manager.state.dict(),
            "decision_log": self.decision_log,
            "cost_log": self.cost_log,
            "session_id": session_id,
            "penalty_log": self.state_manager.state.penalty_log,
        }
        
        logger.info(f"Simulation completed: {round_num} rounds, total cost: {cumulative_total_cost:.2f}")
        return final_report
    
    def _get_visible_flights(self, current_time: ReferenceHour) -> List[Flight]:
        """
        Get flights visible at current time.
        
        Args:
            current_time: Current reference hour
            
        Returns:
            List of visible flights
        """
        # Flights are visible if they are scheduled to depart at or after current time
        # and haven't landed yet (or are in the near future)
        visible = []
        
        for flight in self.state_manager.state.flight_history:
            if (
                flight.scheduled_departure >= current_time
                and (flight.actual_arrival is None or flight.actual_arrival >= current_time)
            ):
                visible.append(flight)
        
        return visible
    
    def _update_state_from_response(
        self, response: Dict, current_time: ReferenceHour
    ) -> None:
        """
        Update game state from API response (HourResponseDto).
        
        Args:
            response: HourResponseDto dictionary
            current_time: Current reference hour
        """
        # Update flight history with new flight events
        flight_updates = response.get("flightUpdates", [])
        for flight_event in flight_updates:
            # Convert FlightEvent to Flight object
            # Map API format to our internal format
            flight_id = flight_event.get("flightId")
            flight_number = flight_event.get("flightNumber", "")
            origin = flight_event.get("originAirport", "")
            destination = flight_event.get("destinationAirport", "")
            
            departure = flight_event.get("departure", {})
            arrival = flight_event.get("arrival", {})
            scheduled_departure = ReferenceHour(
                day=departure.get("day", 0),
                hour=departure.get("hour", 0)
            )
            scheduled_arrival = ReferenceHour(
                day=arrival.get("day", 0),
                hour=arrival.get("hour", 0)
            )
            
            # Convert passengers from camelCase to uppercase
            passengers_api = flight_event.get("passengers", {})
            planned_passengers = {
                "FIRST": passengers_api.get("first", 0),
                "BUSINESS": passengers_api.get("business", 0),
                "PREMIUM_ECONOMY": passengers_api.get("premiumEconomy", 0),
                "ECONOMY": passengers_api.get("economy", 0),
            }
            
            flight = Flight(
                flight_id=flight_id,
                flight_number=flight_number,
                origin=origin,
                destination=destination,
                scheduled_departure=scheduled_departure,
                scheduled_arrival=scheduled_arrival,
                planned_passengers=planned_passengers,
                planned_distance=flight_event.get("distance", 0.0),
                aircraft_type=flight_event.get("aircraftType", ""),
                event_type=flight_event.get("eventType", "SCHEDULED"),
            )
            
            # Update or add to flight history
            existing = None
            for idx, f in enumerate(self.state_manager.state.flight_history):
                if f.flight_id == flight.flight_id:
                    existing = idx
                    break
            
            if existing is not None:
                self.state_manager.state.flight_history[existing] = flight
            else:
                self.state_manager.state.flight_history.append(flight)
        
        # Update penalties (PenaltyDto format)
        penalties = response.get("penalties", [])
        for penalty_data in penalties:
            # PenaltyDto has issuedDay and issuedHour
            issued_day = penalty_data.get("issuedDay", current_time.day)
            issued_hour = penalty_data.get("issuedHour", current_time.hour)
            issued_time = ReferenceHour(day=issued_day, hour=issued_hour)
            
            penalty = PenaltyRecord(
                code=penalty_data.get("code", "UNKNOWN"),
                cost=penalty_data.get("penalty", 0.0),  # API uses "penalty" not "cost"
                reason=penalty_data.get("reason", ""),
                issued_time=issued_time,
            )
            self.state_manager.state.penalty_log.append(penalty)
            # Don't add penalty cost here - totalCost from API already includes all penalties
        
        # Update current time from response (API returns the time we just played)
        response_day = response.get("day", current_time.day)
        response_hour = response.get("hour", current_time.hour)
        # Sync state time with API response time
        self.state_manager.state.current_day = response_day
        self.state_manager.state.current_hour = response_hour
        
        # Update total cost from API response (cumulative total)
        api_total_cost = response.get("totalCost", self.state_manager.state.total_cost)
        self.state_manager.state.total_cost = api_total_cost
    
    def handle_errors(self, exception: Exception) -> None:
        """
        Handle errors during simulation.
        
        Args:
            exception: Exception that occurred
        """
        logger.error(f"Error in simulation: {exception}", exc_info=True)
        # Decide whether to retry or stop
        # For now, we stop on any error
        # Could implement retry logic here

