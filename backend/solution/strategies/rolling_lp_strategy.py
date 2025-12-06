"""Rolling-horizon min-cost flow/MILP strategy for kit loading and purchasing.

This strategy uses a rolling horizon optimization with linear programming to minimize
penalties and transport costs while satisfying demand and capacity constraints.
"""

import logging
from typing import Dict, List, Tuple, Set
from collections import defaultdict

from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.airport import Airport
from models.aircraft import AircraftType
from solution.config import SolutionConfig

logger = logging.getLogger(__name__)

# Try to import PuLP solver
try:
    import pulp
    SOLVER_AVAILABLE = True
except ImportError:
    SOLVER_AVAILABLE = False
    logger.warning("PuLP not available - will use fallback heuristic only")


class RollingLPStrategy:
    """Rolling-horizon linear programming strategy for kit optimization."""
    
    # Class keys as per API spec
    CLASS_KEYS = ["FIRST", "BUSINESS", "PREMIUM_ECONOMY", "ECONOMY"]
    
    # Default lead times (hours) from PENALTY_ANALYSIS.py
    DEFAULT_LEAD_TIMES = {
        "FIRST": 48,
        "BUSINESS": 36,
        "PREMIUM_ECONOMY": 24,
        "ECONOMY": 12,
    }
    
    # Processing times from penalty analysis (hours)
    DEFAULT_PROCESSING_TIMES = {
        "FIRST": 6,
        "BUSINESS": 4,
        "PREMIUM_ECONOMY": 2,
        "ECONOMY": 1,
    }
    
    # Kit costs from config.py
    KIT_COSTS = {
        "FIRST": 50.0,
        "BUSINESS": 30.0,
        "PREMIUM_ECONOMY": 15.0,
        "ECONOMY": 10.0,
    }
    
    def __init__(
        self,
        config: SolutionConfig,
        horizon_hours: int = 36,
        solver_timeout_s: int = 2
    ):
        """
        Initialize rolling LP strategy.
        
        Args:
            config: Solution configuration
            horizon_hours: Planning horizon in hours (24-36)
            solver_timeout_s: Timeout for solver in seconds
        """
        self.config = config
        self.horizon_hours = horizon_hours
        self.solver_timeout_s = solver_timeout_s
        
        logger.info(
            f"RollingLPStrategy initialized: horizon={horizon_hours}h, "
            f"timeout={solver_timeout_s}s, solver_available={SOLVER_AVAILABLE}"
        )
    
    def optimize(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """
        Optimize kit loading and purchasing decisions.
        
        Args:
            state: Current game state
            flights: Upcoming flights
            airports: Airport information
            aircraft_types: Aircraft type information
            
        Returns:
            Tuple of (load_decisions, purchase_orders)
        """
        current_time = ReferenceHour(day=state.current_day, hour=state.current_hour)
        now_hours = current_time.to_hours()
        
        # Try LP solver first if available
        if SOLVER_AVAILABLE:
            try:
                loads, purchases = self._solve_lp(
                    state, flights, airports, aircraft_types, current_time, now_hours
                )
                logger.info(f"LP solution: {len(loads)} loads, {len(purchases)} purchases")
                return loads, purchases
            except Exception as e:
                logger.warning(f"LP solver failed: {e} - falling back to heuristic")
        
        # Fallback to heuristic
        loads, purchases = self._fallback_heuristic(
            state, flights, airports, aircraft_types, current_time, now_hours
        )
        logger.info(f"Heuristic solution: {len(loads)} loads, {len(purchases)} purchases")
        return loads, purchases
    
    def _solve_lp(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
        current_time: ReferenceHour,
        now_hours: int,
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """Solve using linear programming."""
        
        # Build time grid
        horizon_end = now_hours + self.horizon_hours
        time_points = list(range(now_hours, horizon_end + 1))
        
        # Collect relevant airports
        relevant_airports = self._get_relevant_airports(flights, now_hours, horizon_end)
        relevant_airports.add("HUB1")  # Always include hub
        
        # Filter flights in window
        horizon_flights = [
            f for f in flights
            if now_hours <= f.scheduled_departure.to_hours() <= horizon_end
        ]
        
        if not horizon_flights:
            logger.info("No flights in horizon - no decisions needed")
            return [], []
        
        # Create LP problem
        prob = pulp.LpProblem("KitOptimization", pulp.LpMinimize)
        
        # Variables
        load_vars = {}  # (flight_id, class) -> var
        purch_vars = {}  # (hour, class) -> var
        inv_vars = {}  # (airport, hour, class) -> var
        
        # Create variables
        slack_vars = {}  # For unmet demand penalties
        
        for flight in horizon_flights:
            aircraft = aircraft_types.get(flight.aircraft_type)
            if not aircraft:
                continue
            
            for cls in self.CLASS_KEYS:
                capacity = aircraft.kit_capacity.get(cls, 0)
                if capacity > 0:
                    var_name = f"load_{flight.flight_id}_{cls}"
                    load_vars[(flight.flight_id, cls)] = pulp.LpVariable(
                        var_name, lowBound=0, upBound=capacity, cat='Integer'
                    )
                    
                    # Slack variable for unmet demand
                    slack_name = f"slack_{flight.flight_id}_{cls}"
                    slack_vars[(flight.flight_id, cls)] = pulp.LpVariable(
                        slack_name, lowBound=0, cat='Integer'
                    )
        
        # Purchase variables (only at HUB1)
        for t in time_points:
            for cls in self.CLASS_KEYS:
                var_name = f"purch_{t}_{cls}"
                purch_vars[(t, cls)] = pulp.LpVariable(
                    var_name, lowBound=0, cat='Integer'
                )
        
        # We don't need inventory variables with simplified flow balance
        # Storage capacity is implicitly handled by not allowing over-purchase
        
        # Flow balance constraints
        # Simplified: for each airport/class, inventory must support all departures
        for airport_code in relevant_airports:
            airport = airports.get(airport_code)
            if not airport:
                continue
            
            for cls in self.CLASS_KEYS:
                # Initial inventory
                initial_inv = 0
                if airport_code in state.airport_inventories:
                    initial_inv = state.airport_inventories[airport_code].get(cls, 0)
                
                # Total departures from this airport in the horizon
                total_departures = sum(
                    load_vars.get((f.flight_id, cls), 0)
                    for f in horizon_flights
                    if f.origin == airport_code
                )
                
                # Total arrivals to this airport (that finish processing in horizon)
                total_arrivals = 0
                for f in horizon_flights:
                    if f.destination == airport_code:
                        proc_time = airport.processing_times.get(cls, 
                                    self.DEFAULT_PROCESSING_TIMES.get(cls, 2))
                        arrival_ready = f.scheduled_arrival.to_hours() + proc_time
                        # Count if ready within horizon
                        if arrival_ready <= horizon_end:
                            total_arrivals += load_vars.get((f.flight_id, cls), 0)
                
                # Purchases (HUB1 only)
                total_purchases = 0
                if airport_code == "HUB1":
                    lead_time = self.DEFAULT_LEAD_TIMES.get(cls, 24)
                    for t in time_points:
                        # Purchases at time t arrive at t + lead_time
                        if t + lead_time <= horizon_end:
                            total_purchases += purch_vars.get((t, cls), 0)
                
                # Simple balance: initial + arrivals + purchases >= departures
                prob += (
                    initial_inv + total_arrivals + total_purchases >= total_departures
                ), f"Balance_{airport_code}_{cls}"
        
        # Demand coverage constraints (with slack for feasibility)
        for flight in horizon_flights:
            passengers = self._get_passenger_forecast(flight)
            
            for cls in self.CLASS_KEYS:
                pax = passengers.get(cls, 0)
                if pax > 0 and (flight.flight_id, cls) in load_vars:
                    # Add small uplift for outstations (optional)
                    if flight.origin != "HUB1":
                        uplift = max(1, int(pax * 0.05))
                        demand = pax + uplift
                    else:
                        demand = pax
                    
                    # Soft constraint: load + slack >= demand
                    # Slack represents unmet demand (penalized heavily)
                    prob += (
                        load_vars[(flight.flight_id, cls)] + slack_vars[(flight.flight_id, cls)] >= demand
                    ), f"Demand_{flight.flight_id}_{cls}"
        
        # No storage capacity constraints needed with simplified model
        # The balance constraints naturally limit based on available inventory
        
        # Objective: minimize total cost
        cost_expr = 0
        
        # Heavy penalty for unmet demand (slack variables)
        UNFULFILLED_PENALTY = 1000.0  # Very high to avoid unmet demand
        for (flight_id, cls), var in slack_vars.items():
            cost_expr += UNFULFILLED_PENALTY * var
        
        # Loading costs
        for (flight_id, cls), var in load_vars.items():
            flight = next((f for f in horizon_flights if f.flight_id == flight_id), None)
            if flight and flight.origin in airports:
                loading_cost = airports[flight.origin].loading_costs.get(cls, 1.0)
                cost_expr += loading_cost * var
        
        # Purchase costs
        for (t, cls), var in purch_vars.items():
            cost_expr += self.KIT_COSTS[cls] * var
        
        # Processing costs (implicit in arrivals)
        for flight in horizon_flights:
            if flight.destination in airports:
                dest_airport = airports[flight.destination]
                for cls in self.CLASS_KEYS:
                    if (flight.flight_id, cls) in load_vars:
                        proc_cost = dest_airport.processing_costs.get(cls, 1.0)
                        cost_expr += proc_cost * load_vars[(flight.flight_id, cls)]
        
        prob += cost_expr, "TotalCost"
        
        # Solve
        solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=self.solver_timeout_s)
        status = prob.solve(solver)
        
        logger.info(f"LP solver status: {pulp.LpStatus[status]}, objective={pulp.value(prob.objective) if status == pulp.LpStatusOptimal else 'N/A'}")
        
        if status != pulp.LpStatusOptimal:
            logger.warning(f"LP solver status: {pulp.LpStatus[status]}")
            raise Exception(f"LP not optimal: {pulp.LpStatus[status]}")
        
        logger.info(f"LP solver: optimal solution found, cost={pulp.value(prob.objective):.2f}")
        
        # Log slack usage (unmet demand)
        total_slack = sum(pulp.value(var) or 0 for var in slack_vars.values())
        if total_slack > 0:
            logger.warning(f"Unmet demand (slack): {total_slack:.0f} kits total")
        
        # Extract decisions for current hour only
        loads = []
        for flight in horizon_flights:
            if flight.scheduled_departure.to_hours() == now_hours:
                kits = {}
                for cls in self.CLASS_KEYS:
                    if (flight.flight_id, cls) in load_vars:
                        qty = int(pulp.value(load_vars[(flight.flight_id, cls)]) or 0)
                        if qty > 0:
                            kits[cls] = qty
                        
                        # Log slack if any
                        slack = pulp.value(slack_vars.get((flight.flight_id, cls), 0)) or 0
                        if slack > 0:
                            logger.warning(f"  Flight {flight.flight_id} {cls}: loaded={qty}, slack={slack:.0f}")
                
                if kits:
                    loads.append(KitLoadDecision(
                        flight_id=flight.flight_id,
                        kits_per_class=kits
                    ))
        
        # Extract purchase decisions for current hour
        purchases = []
        kits_to_purchase = {}
        for cls in self.CLASS_KEYS:
            if (now_hours, cls) in purch_vars:
                qty = int(pulp.value(purch_vars[(now_hours, cls)]) or 0)
                if qty >= 3:  # Minimum batch size
                    kits_to_purchase[cls] = qty
        
        if kits_to_purchase:
            # Calculate delivery time
            lead_time = max(self.DEFAULT_LEAD_TIMES.get(cls, 24) for cls in kits_to_purchase.keys())
            delivery_hours = now_hours + lead_time
            delivery_time = ReferenceHour(
                day=delivery_hours // 24,
                hour=delivery_hours % 24
            )
            
            purchases.append(KitPurchaseOrder(
                kits_per_class=kits_to_purchase,
                order_time=current_time,
                expected_delivery=delivery_time
            ))
        
        return loads, purchases
    
    def _fallback_heuristic(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
        current_time: ReferenceHour,
        now_hours: int,
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """Fallback heuristic when solver not available or fails."""
        
        loads = []
        
        # Load flights departing now
        for flight in flights:
            if flight.scheduled_departure.to_hours() != now_hours:
                continue
            
            if flight.origin not in state.airport_inventories:
                continue
            
            aircraft = aircraft_types.get(flight.aircraft_type)
            if not aircraft:
                continue
            
            passengers = self._get_passenger_forecast(flight)
            inventory = state.airport_inventories[flight.origin].copy()
            is_hub = (flight.origin == "HUB1")
            is_outstation = not is_hub
            
            kits_to_load = {}
            
            for cls in self.CLASS_KEYS:
                pax = passengers.get(cls, 0)
                if pax <= 0:
                    continue
                
                # Calculate buffer
                if is_hub:
                    buffer = 0  # No buffer at hub
                else:
                    # Outstation: 5% or 1-2 kits
                    buffer = min(2, max(1, int(pax * 0.05)))
                
                needed = pax + buffer
                
                # Pre-positioning for return flights (if this is HUB to outstation)
                preposition = 0
                if is_hub and flight.destination != "HUB1":
                    # Estimate return demand (simplified)
                    dest_inv = state.airport_inventories.get(flight.destination, {}).get(cls, 0)
                    if dest_inv < pax:
                        preposition = max(0, pax - dest_inv)
                        preposition = min(preposition, 5)  # Cap at 5
                
                total_needed = needed + preposition
                capacity = aircraft.kit_capacity.get(cls, 0)
                available = inventory.get(cls, 0)
                
                # Load what we can
                to_load = min(total_needed, capacity, available)
                
                if to_load > 0:
                    kits_to_load[cls] = to_load
                    inventory[cls] = available - to_load
            
            if kits_to_load:
                loads.append(KitLoadDecision(
                    flight_id=flight.flight_id,
                    kits_per_class=kits_to_load
                ))
        
        # Purchase decisions at HUB1
        purchases = []
        horizon_end = now_hours + min(36, self.horizon_hours)
        
        # Calculate demand in horizon for HUB departures
        horizon_demand = defaultdict(int)
        for flight in flights:
            dep_time = flight.scheduled_departure.to_hours()
            if now_hours <= dep_time <= horizon_end and flight.origin == "HUB1":
                passengers = self._get_passenger_forecast(flight)
                for cls, pax in passengers.items():
                    horizon_demand[cls] += pax
        
        # Purchase if needed
        kits_to_purchase = {}
        hub_inv = state.airport_inventories.get("HUB1", {})
        
        for cls in self.CLASS_KEYS:
            current_stock = hub_inv.get(cls, 0)
            demand = horizon_demand[cls]
            
            # Order if below 105% of demand
            if current_stock < demand * 1.05:
                target = int(demand * 1.1)
                needed = max(0, target - current_stock)
                
                # Batch to at least 5 kits
                if needed > 0:
                    needed = max(5, needed)
                    kits_to_purchase[cls] = needed
        
        if kits_to_purchase:
            # Use longest lead time for safety
            lead_time = max(self.DEFAULT_LEAD_TIMES.get(cls, 24) for cls in kits_to_purchase.keys())
            delivery_hours = now_hours + lead_time
            delivery_time = ReferenceHour(
                day=delivery_hours // 24,
                hour=delivery_hours % 24
            )
            
            purchases.append(KitPurchaseOrder(
                kits_per_class=kits_to_purchase,
                order_time=current_time,
                expected_delivery=delivery_time
            ))
        
        return loads, purchases
    
    def _get_relevant_airports(
        self,
        flights: List[Flight],
        start_hour: int,
        end_hour: int
    ) -> Set[str]:
        """Get airports relevant to the planning horizon."""
        airports = set()
        for flight in flights:
            dep_time = flight.scheduled_departure.to_hours()
            if start_hour <= dep_time <= end_hour:
                airports.add(flight.origin)
                airports.add(flight.destination)
        return airports
    
    def _get_passenger_forecast(self, flight: Flight) -> Dict[str, int]:
        """Get passenger forecast for a flight."""
        # Use actual passengers if available, otherwise planned
        if flight.actual_passengers:
            return flight.actual_passengers.copy()
        return flight.planned_passengers.copy()


# Backwards compatibility aliases
GreedyKitStrategy = RollingLPStrategy
OptimalKitStrategy = RollingLPStrategy
PenaltyAwareStrategy = RollingLPStrategy
