"""Rolling-horizon time-expanded MILP strategy for kit loading and purchasing.

This strategy uses a proper time-expanded network with per-hour inventory tracking,
respecting lead times, processing times, and all temporal constraints. Falls back
to a simple greedy heuristic if MILP is infeasible or unavailable.

Key features:
- Extended availability window (72h) for purchases to arrive, separate from loading horizon
- Credits inflow from all arrivals within availability window, including pre-departed flights
- Flexible purchase timing with proper lead time constraints
- Realistic upper bounds based on storage capacity and projected demand
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
        horizon_hours: int = 72,  # 72-hour availability window (48h max lead + 24h buffer)
        solver_timeout_s: int = 2  # 2-second timeout for solver
    ):
        """
        Initialize rolling LP strategy with optimized time-expanded MILP.
        
        Args:
            config: Solution configuration
            horizon_hours: Availability horizon in hours (default 72 to cover lead times)
            solver_timeout_s: Timeout for solver in seconds (default 2)
        """
        self.config = config
        self.horizon_hours = horizon_hours
        self.solver_timeout_s = solver_timeout_s
        
        logger.info(
            f"RollingLPStrategy initialized: horizon={horizon_hours}h, "
            f"timeout={solver_timeout_s}s, solver_available={SOLVER_AVAILABLE}"
        )
    
    def _analyze_recent_penalties(self, state: GameState, lookback_rounds: int = 10) -> Dict[str, float]:
        """
        Analyze recent penalties to adjust purchase targets.
        
        Returns demand multipliers per class based on penalty history.
        If no penalties, returns 1.0. If penalties found, increases to 1.3-1.5.
        """
        multipliers = {cls: 1.0 for cls in self.CLASS_KEYS}
        
        if not state.penalty_log:
            return multipliers
        
        # Count unfulfilled/inventory penalties in recent rounds
        penalty_counts = {cls: 0 for cls in self.CLASS_KEYS}
        
        for penalty in state.penalty_log[-lookback_rounds * 10:]:  # Approximate recent penalties
            reason = penalty.reason.upper()
            
            # Check for inventory/unfulfilled penalties by class
            for cls in self.CLASS_KEYS:
                if cls in reason and ('UNFULFILLED' in reason or 'INVENTORY' in reason or 'SHORTAGE' in reason):
                    penalty_counts[cls] += 1
        
        # Boost purchase targets if penalties detected
        for cls in self.CLASS_KEYS:
            if penalty_counts[cls] > 0:
                # Scale boost: 1-3 penalties -> 1.2x, 4-6 -> 1.3x, 7+ -> 1.5x
                if penalty_counts[cls] >= 7:
                    multipliers[cls] = 1.5
                elif penalty_counts[cls] >= 4:
                    multipliers[cls] = 1.3
                else:
                    multipliers[cls] = 1.2
                logger.info(f"Penalty feedback: {cls} has {penalty_counts[cls]} recent penalties, "
                           f"boosting purchase target to {multipliers[cls]:.1f}x")
        
        return multipliers
    
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
        """
        Solve using time-expanded MILP with extended availability window.
        
        Key improvements:
        - Availability window (72h) covers max lead time + buffer for purchases
        - Credits arrivals from ALL flights landing in window (even if departed earlier)
        - Flexible purchase timing with proper lead time gating
        - Realistic upper bounds based on storage capacity
        """
        
        # Extended availability window for inventory flow (purchases, arrivals)
        availability_end = now_hours + self.horizon_hours  # 72h
        time_points = list(range(now_hours, availability_end + 1))
        
        # Collect relevant airports (for entire availability window)
        relevant_airports = self._get_relevant_airports(flights, now_hours, availability_end)
        relevant_airports.add("HUB1")  # Always include hub
        
        # Flights for LOADING: departing in availability window, not yet departed
        loading_flights = [
            f for f in flights
            if now_hours <= f.scheduled_departure.to_hours() <= availability_end
            and f.event_type in ["SCHEDULED", "CHECKED_IN"]
        ]
        
        # Flights for INFLOW: any flight arriving within availability window
        # CRITICAL: Include DEPARTED flights whose kits will arrive and be processed in time
        inflow_flights = []
        for f in flights:
            if f.destination not in relevant_airports:
                continue
            
            # Allow SCHEDULED, CHECKED_IN, and DEPARTED flights
            if f.event_type not in ["SCHEDULED", "CHECKED_IN", "DEPARTED"]:
                continue
            
            arrival_hour = f.scheduled_arrival.to_hours()
            dest_airport = airports.get(f.destination)
            if not dest_airport:
                continue
            
            # Check if kits become available within availability window
            max_proc = max(dest_airport.processing_times.get(cls, self.DEFAULT_PROCESSING_TIMES.get(cls, 2)) 
                          for cls in self.CLASS_KEYS)
            available_hour = arrival_hour + max_proc
            
            if available_hour <= availability_end:
                inflow_flights.append(f)
        
        if not loading_flights:
            logger.info("No flights in loading horizon - checking purchases only")
        
        logger.info(f"Building MILP: {len(time_points)} hours, "
                   f"{len(relevant_airports)} airports, {len(loading_flights)} loading, "
                   f"{len(inflow_flights)} inflow flights")
        
        # Create MILP problem
        prob = pulp.LpProblem("TimeExpandedKitFlow", pulp.LpMinimize)
        
        # === DECISION VARIABLES ===
        
        # Inventory variables: inv[airport, time, class] (continuous for speed)
        inv_vars = {}
        for airport_code in relevant_airports:
            airport = airports.get(airport_code)
            if not airport:
                continue
            for t in time_points:
                for cls in self.CLASS_KEYS:
                    storage_cap = airport.storage_capacity.get(cls, 1000)
                    var_name = f"inv_{airport_code}_{t}_{cls}"
                    inv_vars[(airport_code, t, cls)] = pulp.LpVariable(
                        var_name, lowBound=0, upBound=storage_cap, cat='Continuous'
                    )
        
        # Load variables: load[flight_id, class] (integer, 0 <= load <= capacity)
        load_vars = {}
        for flight in loading_flights:
            aircraft = aircraft_types.get(flight.aircraft_type)
            if not aircraft:
                logger.warning(f"Aircraft type {flight.aircraft_type} not found for {flight.flight_id}")
                continue
            
            for cls in self.CLASS_KEYS:
                capacity = aircraft.kit_capacity.get(cls, 0)
                if capacity > 0:
                    var_name = f"load_{flight.flight_id}_{cls}"
                    load_vars[(flight.flight_id, cls)] = pulp.LpVariable(
                        var_name, lowBound=0, upBound=capacity, cat='Integer'
                    )
        
        # Purchase variables: purch[delivery_time, class] (integer, >= 0, HUB1 only)
        # Apply penalty feedback to boost purchase targets if recent penalties detected
        penalty_multipliers = self._analyze_recent_penalties(state)
        
        # Calculate total demand over availability window from HUB
        # CRITICAL: Use ALL flights in availability window, not just loading_flights
        # This prevents demand from disappearing as time progresses
        hub_demand = defaultdict(int)
        hub_flights_count = 0
        for flight in flights:  # Use full flights list, not just loading_flights
            dep_time = flight.scheduled_departure.to_hours()
            # Include any flight departing from HUB within availability window
            if now_hours <= dep_time <= availability_end and flight.origin == "HUB1":
                hub_flights_count += 1
                passengers = self._get_passenger_forecast(flight)
                for cls in self.CLASS_KEYS:
                    hub_demand[cls] += passengers.get(cls, 0)
        
        # FALLBACK: If no future HUB flights visible, estimate demand based on recent history
        # This prevents purchases from stopping when flight visibility is limited
        if hub_flights_count == 0:
            logger.warning(f"No HUB flights in availability window - using historical demand estimate")
            # Estimate: assume ~10 flights per day from HUB, typical passenger load
            estimated_flights_per_day = 10
            days_in_window = self.horizon_hours / 24.0
            estimated_total_flights = int(estimated_flights_per_day * days_in_window)
            
            # Typical passenger distribution (conservative estimates)
            hub_demand["FIRST"] = estimated_total_flights * 5
            hub_demand["BUSINESS"] = estimated_total_flights * 10
            hub_demand["PREMIUM_ECONOMY"] = estimated_total_flights * 20
            hub_demand["ECONOMY"] = estimated_total_flights * 50
            
            logger.info(f"Estimated HUB demand (no visible flights): {dict(hub_demand)}")
        else:
            logger.info(f"HUB demand from {hub_flights_count} flights in window: {dict(hub_demand)}")
        
        purch_vars = {}
        hub1_storage = airports.get("HUB1", None)
        
        # Create purchase variables for each delivery time (not order time)
        # Purchases ordered "now" arrive at now + lead_time
        for t in time_points:
            for cls in self.CLASS_KEYS:
                lead_time = self.DEFAULT_LEAD_TIMES.get(cls, 24)
                order_time = t - lead_time
                
                # Allow orders placed from now through the availability window
                # This ensures purchases can arrive even after the short decision horizon
                if order_time < now_hours or order_time > availability_end:
                    continue
                
                # Upper bound: storage capacity minus current inventory
                storage_cap = hub1_storage.storage_capacity.get(cls, 10000) if hub1_storage else 10000
                current_inv = state.airport_inventories.get("HUB1", {}).get(cls, 0)
                
                # Apply penalty multiplier to effective demand
                effective_demand = int(hub_demand[cls] * penalty_multipliers[cls])
                
                # Generous upper bound: ensure we always have room to purchase
                # Even if demand is 0, allow purchasing up to storage capacity
                if effective_demand == 0:
                    # No immediate demand: allow modest purchases (e.g., up to 50% of storage)
                    upper_bound = max(500, storage_cap // 2)
                else:
                    # Have demand: storage - current_inv + effective_demand
                    upper_bound = max(
                        500,  # Minimum reasonable bound
                        min(storage_cap * 2, storage_cap - current_inv + effective_demand)
                    )
                
                # Final cap: never exceed 2x storage (allows some flexibility)
                upper_bound = min(upper_bound, storage_cap * 2)
                
                var_name = f"purch_{t}_{cls}"
                purch_vars[(t, cls)] = pulp.LpVariable(
                    var_name, lowBound=0, upBound=upper_bound, cat='Integer'
                )
        
        # === CONSTRAINTS ===
        
        # 1. Initial inventory at t=now
        for airport_code in relevant_airports:
            if airport_code not in state.airport_inventories:
                continue
            for cls in self.CLASS_KEYS:
                if (airport_code, now_hours, cls) in inv_vars:
                    initial_inv = state.airport_inventories[airport_code].get(cls, 0)
                    
                    # Add in-process kits that arrive exactly at now
                    if airport_code in state.in_process_kits:
                        for movement in state.in_process_kits[airport_code]:
                            # Handle both object and dict formats
                            if hasattr(movement, 'execute_time'):
                                exec_time = movement.execute_time.to_hours()
                            elif isinstance(movement, dict):
                                exec_dict = movement.get('execute_time', {})
                                exec_time = exec_dict.get('day', 0) * 24 + exec_dict.get('hour', 0)
                            else:
                                exec_time = 0
                            
                            if exec_time == now_hours:
                                if hasattr(movement, 'kits_per_class'):
                                    initial_inv += movement.kits_per_class.get(cls, 0)
                                elif isinstance(movement, dict):
                                    kits = movement.get('kits_per_class', {})
                                    initial_inv += kits.get(cls, 0)
                    
                    prob += (
                        inv_vars[(airport_code, now_hours, cls)] == initial_inv
                    ), f"InitInv_{airport_code}_{cls}"
        
        # 2. Flow balance per hour: inv[a,t+1,k] = inv[a,t,k] - departures + arrivals + purchases
        for airport_code in relevant_airports:
            airport = airports.get(airport_code)
            if not airport:
                continue
            
            for cls in self.CLASS_KEYS:
                for i in range(len(time_points) - 1):
                    t = time_points[i]
                    t_next = time_points[i + 1]
                    
                    if (airport_code, t, cls) not in inv_vars or (airport_code, t_next, cls) not in inv_vars:
                        continue
                    
                    # Start with inventory at time t
                    flow_expr = inv_vars[(airport_code, t, cls)]
                    
                    # Subtract loads departing at hour t from this airport
                    for flight in loading_flights:
                        if flight.origin == airport_code and flight.scheduled_departure.to_hours() == t:
                            if (flight.flight_id, cls) in load_vars:
                                flow_expr -= load_vars[(flight.flight_id, cls)]
                    
                    # Add arrivals that become available at t_next (after processing)
                    # CRITICAL: Use inflow_flights which includes DEPARTED flights
                    for flight in inflow_flights:
                        if flight.destination == airport_code:
                            arrival_hour = flight.scheduled_arrival.to_hours()
                            proc_time = airport.processing_times.get(cls, 
                                        self.DEFAULT_PROCESSING_TIMES.get(cls, 2))
                            available_hour = arrival_hour + proc_time
                            
                            # Kits become available at arrival + processing time
                            if available_hour == t_next:
                                # For departed flights, use fallback estimate (no load_vars)
                                if (flight.flight_id, cls) in load_vars:
                                    flow_expr += load_vars[(flight.flight_id, cls)]
                                else:
                                    # Fallback: estimate based on planned passengers and capacity
                                    aircraft = aircraft_types.get(flight.aircraft_type)
                                    if aircraft:
                                        passengers = self._get_passenger_forecast(flight)
                                        capacity = aircraft.kit_capacity.get(cls, 0)
                                        # Assume loaded min(passengers, capacity)
                                        estimated_kits = min(passengers.get(cls, 0), capacity)
                                        if estimated_kits > 0:
                                            flow_expr += estimated_kits
                    
                    # Add purchases arriving at t_next (HUB1 only)
                    # purch_vars[(t_next, cls)] represents kits arriving at t_next
                    if airport_code == "HUB1" and (t_next, cls) in purch_vars:
                        flow_expr += purch_vars[(t_next, cls)]
                    
                    # CRITICAL: Add ALL confirmed in-process movements arriving at t_next
                    # This includes both purchases and flight arrivals already in the system
                    if airport_code in state.in_process_kits:
                        for movement in state.in_process_kits[airport_code]:
                            # Extract execute time from movement (when kits become available)
                            if hasattr(movement, 'execute_time'):
                                exec_time = movement.execute_time.to_hours()
                            elif isinstance(movement, dict):
                                exec_dict = movement.get('execute_time', {})
                                exec_time = exec_dict.get('day', 0) * 24 + exec_dict.get('hour', 0)
                            else:
                                exec_time = 0
                            
                            # If this movement completes at t_next, add its kits to inflow
                            if exec_time == t_next:
                                if hasattr(movement, 'kits_per_class'):
                                    qty = movement.kits_per_class.get(cls, 0)
                                    if qty > 0:
                                        flow_expr += qty
                                elif isinstance(movement, dict):
                                    kits = movement.get('kits_per_class', {})
                                    qty = kits.get(cls, 0)
                                    if qty > 0:
                                        flow_expr += qty
                    
                    # Also check pending_movements for this airport and time
                    for movement in state.pending_movements:
                        # Check if this movement is for this airport
                        move_airport = getattr(movement, 'airport', None)
                        if isinstance(movement, dict):
                            move_airport = movement.get('airport', '')
                        
                        if move_airport == airport_code:
                            # Extract execute time
                            if hasattr(movement, 'execute_time'):
                                exec_time = movement.execute_time.to_hours()
                            elif isinstance(movement, dict):
                                exec_dict = movement.get('execute_time', {})
                                exec_time = exec_dict.get('day', 0) * 24 + exec_dict.get('hour', 0)
                            else:
                                exec_time = 0
                            
                            if exec_time == t_next:
                                if hasattr(movement, 'kits_per_class'):
                                    qty = movement.kits_per_class.get(cls, 0)
                                    if qty > 0:
                                        flow_expr += qty
                                elif isinstance(movement, dict):
                                    kits = movement.get('kits_per_class', {})
                                    qty = kits.get(cls, 0)
                                    if qty > 0:
                                        flow_expr += qty
                    
                    # Constraint: inv[t+1] = flow expression
                    prob += (
                        inv_vars[(airport_code, t_next, cls)] == flow_expr
                    ), f"Flow_{airport_code}_{t}_{cls}"
        
        # 3. Demand constraints: load >= passengers (minimal buffers: HUB=0, outstation=0 or +1)
        for flight in loading_flights:
            passengers = self._get_passenger_forecast(flight)
            
            # Skip flights with unknown aircraft type to avoid infeasibility
            if flight.aircraft_type not in aircraft_types:
                logger.warning(f"Skipping {flight.flight_id}: unknown aircraft type {flight.aircraft_type}")
                continue
            
            for cls in self.CLASS_KEYS:
                pax = passengers.get(cls, 0)
                if pax <= 0:
                    continue
                
                if (flight.flight_id, cls) not in load_vars:
                    continue
                
                # Buffer: HUB=0, outstation=0 (can add +1 if absolutely needed)
                # Start with exact coverage
                buffer = 0
                demand = pax + buffer
                
                # HARD constraint: load >= demand
                prob += (
                    load_vars[(flight.flight_id, cls)] >= demand
                ), f"Demand_{flight.flight_id}_{cls}"
        
        # 4. Aircraft capacity constraints (already handled by variable bounds)
        # 5. Storage capacity constraints (already handled by variable bounds)
        
        # === OBJECTIVE: MINIMIZE TOTAL COST ===
        
        cost_expr = 0
        
        # Transport costs (fuel + distance) with moderate scaling
        for flight in loading_flights:
            aircraft = aircraft_types.get(flight.aircraft_type)
            if not aircraft:
                continue
            
            distance = getattr(flight, 'planned_distance', 1000)
            fuel_cost_per_km = aircraft.fuel_cost_per_km
            
            for cls in self.CLASS_KEYS:
                if (flight.flight_id, cls) not in load_vars:
                    continue
                
                # Transport cost: moderate scaling to avoid dominating objective
                # weight * distance * fuel_cost_per_km * small_scale_factor
                kit_weight = 10.0  # kg per kit
                transport_cost_per_kit = kit_weight * distance * fuel_cost_per_km * 0.005
                
                cost_expr += transport_cost_per_kit * load_vars[(flight.flight_id, cls)]
        
        # Loading costs
        for flight in loading_flights:
            if flight.origin not in airports:
                continue
            
            origin_airport = airports[flight.origin]
            for cls in self.CLASS_KEYS:
                if (flight.flight_id, cls) not in load_vars:
                    continue
                
                loading_cost = origin_airport.loading_costs.get(cls, 1.0)
                cost_expr += loading_cost * load_vars[(flight.flight_id, cls)]
        
        # Processing costs
        for flight in loading_flights:
            if flight.destination not in airports:
                continue
            
            dest_airport = airports[flight.destination]
            for cls in self.CLASS_KEYS:
                if (flight.flight_id, cls) not in load_vars:
                    continue
                
                proc_cost = dest_airport.processing_costs.get(cls, 1.0)
                cost_expr += proc_cost * load_vars[(flight.flight_id, cls)]
        
        # Purchasing costs
        for (t, cls), var in purch_vars.items():
            kit_cost = self.KIT_COSTS.get(cls, 10.0)
            cost_expr += kit_cost * var
        
        # Very small inventory holding cost to discourage excess
        HOLDING_COST = 0.01
        for (airport_code, t, cls), var in inv_vars.items():
            cost_expr += HOLDING_COST * var
        
        # Ensure objective is not zero (add tiny constant if needed)
        if cost_expr == 0:
            logger.warning("Objective is zero - adding minimal constant")
            cost_expr = 0.001
        
        prob += cost_expr, "TotalCost"
        
        # Check if we have any decision variables
        num_vars = len(load_vars) + len(purch_vars)
        if num_vars == 0:
            logger.warning("No decision variables - skipping MILP, using heuristic")
            raise Exception("No decision variables to optimize")
        
        logger.info(f"MILP has {len(load_vars)} load vars, {len(purch_vars)} purchase vars")
        
        # === SOLVE ===
        
        solver = pulp.PULP_CBC_CMD(
            msg=0,
            timeLimit=self.solver_timeout_s,
            threads=2,
            options=['presolve on', 'cuts on', 'heuristics on']
        )
        
        logger.info(f"Solving MILP with timeout={self.solver_timeout_s}s...")
        status = prob.solve(solver)
        
        status_name = pulp.LpStatus[status]
        obj_value = pulp.value(prob.objective) if status == pulp.LpStatusOptimal else None
        
        # Log total purchases across all delivery times for debugging
        total_purchases = {cls: 0 for cls in self.CLASS_KEYS}
        if status == pulp.LpStatusOptimal:
            for (t, cls), var in purch_vars.items():
                qty = int(pulp.value(var) or 0)
                total_purchases[cls] += qty
        
        logger.info(f"MILP status: {status_name}, objective={obj_value}, "
                   f"total_purchases={total_purchases}")
        
        # Discard LP results if not optimal/feasible
        if status != pulp.LpStatusOptimal:
            logger.warning(f"MILP not optimal: {status_name} - falling back to heuristic")
            raise Exception(f"MILP solver failed: {status_name}")
        
        # === EXTRACT DECISIONS ===
        
        # Extract load decisions: only for flights departing NOW
        loads = []
        for flight in loading_flights:
            if flight.scheduled_departure.to_hours() != now_hours:
                continue
            
            kits = {}
            for cls in self.CLASS_KEYS:
                if (flight.flight_id, cls) in load_vars:
                    qty = int(pulp.value(load_vars[(flight.flight_id, cls)]) or 0)
                    if qty > 0:
                        kits[cls] = qty
            
            if kits:
                loads.append(KitLoadDecision(
                    flight_id=flight.flight_id,
                    kits_per_class=kits
                ))
        
        # Extract purchase decisions: 
        # purch_vars[(t, cls)] = kits arriving at time t
        # We need to place order NOW for kits that should arrive at t = now + lead_time
        purchases = []
        kits_to_purchase = {}
        
        # Log all non-zero purchases for debugging
        all_purchases = {}
        for (t, cls), var in purch_vars.items():
            qty = int(pulp.value(var) or 0)
            if qty > 0:
                if t not in all_purchases:
                    all_purchases[t] = {}
                all_purchases[t][cls] = qty
        
        if all_purchases:
            logger.info(f"MILP purchases by delivery time: {all_purchases}")
        
        # Collect purchases for each class where order should be placed now
        for cls in self.CLASS_KEYS:
            lead_time = self.DEFAULT_LEAD_TIMES.get(cls, 24)
            delivery_time = now_hours + lead_time
            
            if (delivery_time, cls) in purch_vars:
                qty = int(pulp.value(purch_vars[(delivery_time, cls)]) or 0)
                if qty > 0:
                    kits_to_purchase[cls] = qty
        
        if kits_to_purchase:
            # Calculate delivery time based on lead times
            max_lead_time = max(
                self.DEFAULT_LEAD_TIMES.get(cls, 24)
                for cls in kits_to_purchase.keys()
            )
            delivery_hours = now_hours + max_lead_time
            delivery_time = ReferenceHour(
                day=delivery_hours // 24,
                hour=delivery_hours % 24
            )
            
            purchases.append(KitPurchaseOrder(
                kits_per_class=kits_to_purchase,
                order_time=current_time,
                expected_delivery=delivery_time
            ))
            
            logger.info(
                f"MILP purchase order: {kits_to_purchase}, "
                f"delivery at {delivery_time.day}d{delivery_time.hour}h"
            )
        else:
            logger.info("MILP: No purchases needed")
        
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
        """
        Fallback greedy heuristic when MILP solver fails or unavailable.
        
        Simple strategy:
        - Load demand with minimal buffer
        - Purchase to maintain safety stock
        - Do NOT assume future purchases are available now
        """
        
        logger.info("Using fallback heuristic")
        
        loads = []
        
        # Load flights departing NOW only
        for flight in flights:
            if flight.scheduled_departure.to_hours() != now_hours:
                continue
            
            if flight.origin not in state.airport_inventories:
                continue
            
            aircraft = aircraft_types.get(flight.aircraft_type)
            if not aircraft:
                continue
            
            passengers = self._get_passenger_forecast(flight)
            available_inv = state.airport_inventories[flight.origin].copy()
            
            kits_to_load = {}
            
            for cls in self.CLASS_KEYS:
                pax = passengers.get(cls, 0)
                if pax <= 0:
                    continue
                
                # Minimal uplift: just cover passengers
                needed = pax
                capacity = aircraft.kit_capacity.get(cls, 0)
                available = available_inv.get(cls, 0)
                
                # Load what we can (cannot exceed available inventory or capacity)
                to_load = min(needed, capacity, available)
                
                if to_load > 0:
                    kits_to_load[cls] = to_load
            
            if kits_to_load:
                loads.append(KitLoadDecision(
                    flight_id=flight.flight_id,
                    kits_per_class=kits_to_load
                ))
        
        # Purchase decisions at HUB1 with penalty feedback
        purchases = []
        horizon_end = now_hours + self.horizon_hours
        
        # Apply penalty feedback to adjust targets
        penalty_multipliers = self._analyze_recent_penalties(state)
        
        # Calculate demand in horizon for HUB departures
        horizon_demand = defaultdict(int)
        hub_flights_count = 0
        for flight in flights:
            dep_time = flight.scheduled_departure.to_hours()
            if now_hours <= dep_time <= horizon_end and flight.origin == "HUB1":
                hub_flights_count += 1
                passengers = self._get_passenger_forecast(flight)
                for cls, pax in passengers.items():
                    horizon_demand[cls] += pax
        
        # FALLBACK: Estimate demand if no visible flights
        if hub_flights_count == 0:
            logger.warning("Heuristic: No HUB flights visible - using demand estimates")
            estimated_flights_per_day = 10
            days_in_window = self.horizon_hours / 24.0
            estimated_total_flights = int(estimated_flights_per_day * days_in_window)
            
            horizon_demand["FIRST"] = estimated_total_flights * 5
            horizon_demand["BUSINESS"] = estimated_total_flights * 10
            horizon_demand["PREMIUM_ECONOMY"] = estimated_total_flights * 20
            horizon_demand["ECONOMY"] = estimated_total_flights * 50
        
        # Purchase if stock + confirmed_in_transit < horizon_demand * margin
        kits_to_purchase = {}
        hub_inv = state.airport_inventories.get("HUB1", {})
        
        for cls in self.CLASS_KEYS:
            current_stock = hub_inv.get(cls, 0)
            demand = horizon_demand[cls]
            
            # Calculate in-transit (only confirmed arrivals, not future purchases)
            in_transit = 0
            if "HUB1" in state.in_process_kits:
                for movement in state.in_process_kits["HUB1"]:
                    if hasattr(movement, 'kits_per_class'):
                        in_transit += movement.kits_per_class.get(cls, 0)
                    elif isinstance(movement, dict):
                        in_transit += movement.get('kits_per_class', {}).get(cls, 0)
            
            total_available = current_stock + in_transit
            
            # Apply penalty multiplier to demand threshold
            safety_margin = 1.1 * penalty_multipliers[cls]
            target_margin = 1.2 * penalty_multipliers[cls]
            
            # Order if below safety threshold
            if total_available < demand * safety_margin:
                target = int(demand * target_margin)
                needed = max(0, target - total_available)
                
                # Batch to at least 5 kits
                if needed > 0:
                    needed = max(5, needed)
                    kits_to_purchase[cls] = needed
        
        if kits_to_purchase:
            # Use default lead time (24h as safe default)
            default_lead_time = 24
            delivery_hours = now_hours + default_lead_time
            delivery_time = ReferenceHour(
                day=delivery_hours // 24,
                hour=delivery_hours % 24
            )
            
            purchases.append(KitPurchaseOrder(
                kits_per_class=kits_to_purchase,
                order_time=current_time,
                expected_delivery=delivery_time
            ))
            
            logger.info(
                f"Heuristic purchase: {kits_to_purchase}, "
                f"delivery at {delivery_time.day}d{delivery_time.hour}h"
            )
        
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
    
    def _calculate_horizon_demand(self, flights: List[Flight]) -> Dict[str, int]:
        """Calculate total demand across all horizon flights per class."""
        demand = {cls: 0 for cls in self.CLASS_KEYS}
        for flight in flights:
            passengers = self._get_passenger_forecast(flight)
            for cls in self.CLASS_KEYS:
                demand[cls] += passengers.get(cls, 0)
        return demand
    
    def _get_passenger_forecast(self, flight: Flight) -> Dict[str, int]:
        """Get passenger forecast for a flight - use actual if available, else planned."""
        # Use actual passengers if available (for checked-in flights), otherwise planned
        if flight.actual_passengers:
            return flight.actual_passengers.copy()
        return flight.planned_passengers.copy()
