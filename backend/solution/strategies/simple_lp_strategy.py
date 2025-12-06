"""Simple MILP strategy - clean and modular."""

import logging
from typing import Dict, List, Tuple
from collections import defaultdict

from models.game_state import GameState
from models.flight import Flight, ReferenceHour
from models.kit import KitLoadDecision, KitPurchaseOrder
from models.airport import Airport
from models.aircraft import AircraftType
from solution.config import SolutionConfig

logger = logging.getLogger(__name__)

try:
    import pulp
    SOLVER_AVAILABLE = True
except ImportError:
    SOLVER_AVAILABLE = False
    logger.warning("PuLP not available")


class SimpleLPStrategy:
    """Simple MILP strategy for kit optimization."""
    
    CLASS_KEYS = ["FIRST", "BUSINESS", "PREMIUM_ECONOMY", "ECONOMY"]
    
    LEAD_TIMES = {"FIRST": 48, "BUSINESS": 36, "PREMIUM_ECONOMY": 24, "ECONOMY": 12}
    PROCESSING_TIMES = {"FIRST": 6, "BUSINESS": 4, "PREMIUM_ECONOMY": 2, "ECONOMY": 1}
    KIT_COSTS = {"FIRST": 50.0, "BUSINESS": 30.0, "PREMIUM_ECONOMY": 15.0, "ECONOMY": 10.0}
    
    def __init__(self, config: SolutionConfig, horizon_hours: int = 72, solver_timeout_s: int = 2):
        self.config = config
        self.horizon_hours = horizon_hours
        self.solver_timeout_s = solver_timeout_s
        logger.info(f"SimpleLPStrategy: horizon={horizon_hours}h, timeout={solver_timeout_s}s")
    
    def optimize(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """Main optimization entry point."""
        current_time = ReferenceHour(day=state.current_day, hour=state.current_hour)
        now_hours = current_time.to_hours()
        
        logger.info(f"Optimizing at {current_time.day}d{current_time.hour}h ({now_hours}h)")
        
        if not SOLVER_AVAILABLE:
            return self._simple_greedy(state, flights, aircraft_types, now_hours)
        
        try:
            return self._solve_milp(state, flights, airports, aircraft_types, current_time, now_hours)
        except Exception as e:
            logger.warning(f"MILP failed: {e}, using greedy")
            return self._simple_greedy(state, flights, aircraft_types, now_hours)
    
    def _solve_milp(
        self,
        state: GameState,
        flights: List[Flight],
        airports: Dict[str, Airport],
        aircraft_types: Dict[str, AircraftType],
        current_time: ReferenceHour,
        now_hours: int,
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """Solve using MILP."""
        
        # Step 1: Filter flights
        loading_flights = self._get_loading_flights(flights, now_hours)
        logger.info(f"Loading flights: {len(loading_flights)}")
        
        # Step 2: Calculate demand
        hub_demand = self._calculate_hub_demand(flights, now_hours)
        logger.info(f"HUB demand: {dict(hub_demand)}")
        
        # Step 3: Build and solve MILP
        prob = pulp.LpProblem("KitFlow", pulp.LpMinimize)
        
        load_vars = self._create_load_variables(loading_flights, aircraft_types)
        purch_vars = self._create_purchase_variables(state, airports, hub_demand, now_hours)
        
        logger.info(f"Variables: {len(load_vars)} loads, {len(purch_vars)} purchases")
        
        if len(load_vars) == 0 and len(purch_vars) == 0:
            logger.warning("No variables to optimize")
            return [], []
        
        # Add constraints
        self._add_demand_constraints(prob, loading_flights, load_vars, aircraft_types)
        self._add_inventory_constraints(prob, state, loading_flights, load_vars, purch_vars, airports, now_hours)
        
        # Set objective
        cost_expr = self._build_objective(load_vars, purch_vars, loading_flights, airports)
        prob += cost_expr, "TotalCost"
        
        # Solve
        solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=self.solver_timeout_s)
        status = prob.solve(solver)
        
        if status != pulp.LpStatusOptimal:
            logger.warning(f"MILP status: {pulp.LpStatus[status]}")
            raise Exception(f"Not optimal: {pulp.LpStatus[status]}")
        
        logger.info(f"MILP optimal, obj={pulp.value(prob.objective):.2f}")
        
        # Extract decisions
        loads = self._extract_loads(loading_flights, load_vars, now_hours)
        purchases = self._extract_purchases(purch_vars, current_time, now_hours)
        
        logger.info(f"Solution: {len(loads)} loads, {len(purchases)} purchases")
        return loads, purchases
    
    def _get_loading_flights(self, flights: List[Flight], now_hours: int) -> List[Flight]:
        """Get flights departing in the next 72 hours that can be loaded."""
        end_hours = now_hours + self.horizon_hours
        loading = []
        for f in flights:
            if f.event_type not in ["SCHEDULED", "CHECKED_IN"]:
                continue
            dep = f.scheduled_departure.to_hours()
            if now_hours <= dep <= end_hours:
                loading.append(f)
        return loading
    
    def _calculate_hub_demand(self, flights: List[Flight], now_hours: int) -> Dict[str, int]:
        """Calculate total demand for HUB departures in planning window."""
        end_hours = now_hours + self.horizon_hours
        demand = defaultdict(int)
        count = 0
        
        for f in flights:
            if f.origin != "HUB1":
                continue
            dep = f.scheduled_departure.to_hours()
            if now_hours <= dep <= end_hours:
                count += 1
                passengers = f.actual_passengers if f.actual_passengers else f.planned_passengers
                for cls in self.CLASS_KEYS:
                    demand[cls] += passengers.get(cls, 0)
        
        # Fallback if no flights visible
        if count == 0:
            logger.warning("No HUB flights - using estimates")
            days = self.horizon_hours / 24.0
            flights_estimate = int(10 * days)
            demand["FIRST"] = flights_estimate * 5
            demand["BUSINESS"] = flights_estimate * 10
            demand["PREMIUM_ECONOMY"] = flights_estimate * 20
            demand["ECONOMY"] = flights_estimate * 50
        
        return demand
    
    def _create_load_variables(
        self, 
        flights: List[Flight], 
        aircraft_types: Dict[str, AircraftType]
    ) -> Dict:
        """Create load decision variables."""
        load_vars = {}
        for flight in flights:
            aircraft = aircraft_types.get(flight.aircraft_type)
            if not aircraft:
                continue
            for cls in self.CLASS_KEYS:
                capacity = aircraft.kit_capacity.get(cls, 0)
                if capacity > 0:
                    load_vars[(flight.flight_id, cls)] = pulp.LpVariable(
                        f"load_{flight.flight_id}_{cls}",
                        lowBound=0,
                        upBound=capacity,
                        cat='Integer'
                    )
        return load_vars
    
    def _create_purchase_variables(
        self,
        state: GameState,
        airports: Dict[str, Airport],
        hub_demand: Dict[str, int],
        now_hours: int
    ) -> Dict:
        """Create purchase decision variables."""
        purch_vars = {}
        hub1 = airports.get("HUB1")
        if not hub1:
            return purch_vars
        
        for cls in self.CLASS_KEYS:
            lead_time = self.LEAD_TIMES[cls]
            delivery_hour = now_hours + lead_time
            
            # Upper bound: generous but realistic
            storage = hub1.storage_capacity.get(cls, 10000)
            current = state.airport_inventories.get("HUB1", {}).get(cls, 0)
            demand = hub_demand[cls]
            
            upper = min(storage * 2, max(1000, storage - current + demand * 2))
            
            purch_vars[(delivery_hour, cls)] = pulp.LpVariable(
                f"purch_{delivery_hour}_{cls}",
                lowBound=0,
                upBound=upper,
                cat='Integer'
            )
        
        return purch_vars
    
    def _add_demand_constraints(
        self,
        prob,
        flights: List[Flight],
        load_vars: Dict,
        aircraft_types: Dict[str, AircraftType]
    ):
        """Add demand constraints: load >= passengers."""
        for flight in flights:
            if flight.aircraft_type not in aircraft_types:
                continue
            
            passengers = flight.actual_passengers if flight.actual_passengers else flight.planned_passengers
            
            for cls in self.CLASS_KEYS:
                pax = passengers.get(cls, 0)
                if pax <= 0:
                    continue
                if (flight.flight_id, cls) not in load_vars:
                    continue
                
                prob += (
                    load_vars[(flight.flight_id, cls)] >= pax
                ), f"demand_{flight.flight_id}_{cls}"
    
    def _add_inventory_constraints(
        self,
        prob,
        state: GameState,
        flights: List[Flight],
        load_vars: Dict,
        purch_vars: Dict,
        airports: Dict[str, Airport],
        now_hours: int
    ):
        """Add inventory constraints with time-awareness for lead times."""
        hub1 = airports.get("HUB1")
        if not hub1:
            return
        
        for cls in self.CLASS_KEYS:
            lead_time = self.LEAD_TIMES[cls]
            
            # Current inventory at HUB1
            current_inv = state.airport_inventories.get("HUB1", {}).get(cls, 0)
            
            # Calculate loads that happen BEFORE purchases arrive
            # These loads must be covered by current inventory + inflow
            early_loads = pulp.lpSum([
                load_vars[(f.flight_id, cls)]
                for f in flights
                if f.origin == "HUB1" 
                and (f.flight_id, cls) in load_vars
                and f.scheduled_departure.to_hours() < now_hours + lead_time
            ])
            
            # Calculate inflow that arrives before purchases
            early_inflow = 0
            for movement in state.pending_movements:
                if movement.destination == "HUB1" and movement.class_type == cls:
                    arrival_hour = movement.arrival_time.to_hours()
                    if arrival_hour < now_hours + lead_time:
                        early_inflow += movement.quantity
            
            # Constraint: early loads must be covered without purchases
            # This forces MILP to buy if current stock is insufficient
            if early_loads != 0:  # Only add if there are early loads
                prob += (
                    current_inv + early_inflow >= early_loads
                ), f"early_inventory_HUB1_{cls}"
                logger.debug(f"Early constraint {cls}: inv={current_inv}, inflow={early_inflow}, early_loads exists")
            
            # Now add constraint for ALL loads (including those after purchase delivery)
            total_load = pulp.lpSum([
                load_vars[(f.flight_id, cls)]
                for f in flights
                if f.origin == "HUB1" and (f.flight_id, cls) in load_vars
            ])
            
            # Total inflow
            total_inflow = 0
            for movement in state.pending_movements:
                if movement.destination == "HUB1" and movement.class_type == cls:
                    arrival_hour = movement.arrival_time.to_hours()
                    if arrival_hour <= now_hours + self.horizon_hours:
                        total_inflow += movement.quantity
            
            # Total purchases (available after lead time)
            total_purch = pulp.lpSum([
                var for (t, c), var in purch_vars.items() if c == cls
            ])
            
            # Constraint: total available >= total loads
            prob += (
                current_inv + total_inflow + total_purch >= total_load
            ), f"total_inventory_HUB1_{cls}"
            
            logger.debug(f"Total constraint {cls}: inv={current_inv}, inflow={total_inflow}, purch_vars={len([k for k in purch_vars.keys() if k[1]==cls])}")    
    def _build_objective(
        self,
        load_vars: Dict,
        purch_vars: Dict,
        flights: List[Flight],
        airports: Dict[str, Airport]
    ) -> pulp.LpAffineExpression:
        """Build cost objective."""
        cost = 0
        
        # Loading costs
        for flight in flights:
            origin = airports.get(flight.origin)
            if not origin:
                continue
            for cls in self.CLASS_KEYS:
                if (flight.flight_id, cls) in load_vars:
                    loading_cost = origin.loading_costs.get(cls, 1.0)
                    cost += loading_cost * load_vars[(flight.flight_id, cls)]
        
        # Purchase costs
        for (t, cls), var in purch_vars.items():
            cost += self.KIT_COSTS[cls] * var
        
        return cost if cost != 0 else 0.001
    
    def _extract_loads(
        self,
        flights: List[Flight],
        load_vars: Dict,
        now_hours: int
    ) -> List[KitLoadDecision]:
        """Extract load decisions for flights departing NOW."""
        loads = []
        for flight in flights:
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
        
        return loads
    
    def _extract_purchases(
        self,
        purch_vars: Dict,
        current_time: ReferenceHour,
        now_hours: int
    ) -> List[KitPurchaseOrder]:
        """Extract purchase orders placed NOW with correct lead times."""
        purchases = []
        
        for cls in self.CLASS_KEYS:
            total_qty = 0
            lead_time = self.LEAD_TIMES[cls]
            
            # Sum all purchases for this class across all delivery times
            for (t, c), var in purch_vars.items():
                if c == cls:
                    qty = int(pulp.value(var) or 0)
                    total_qty += qty
            
            if total_qty > 0:
                # Calculate delivery time based on lead time for this class
                delivery_hours = now_hours + lead_time
                delivery_time = ReferenceHour(
                    day=delivery_hours // 24,
                    hour=delivery_hours % 24
                )
                
                purchases.append(KitPurchaseOrder(
                    kits_per_class={cls: total_qty},
                    delivery_time=delivery_time
                ))
                
                logger.info(f"Purchase: {total_qty} {cls} kits → delivery at {delivery_time.day}d{delivery_time.hour}h")
        
        return purchases
    
    def _simple_greedy(
        self,
        state: GameState,
        flights: List[Flight],
        aircraft_types: Dict[str, AircraftType],
        now_hours: int
    ) -> Tuple[List[KitLoadDecision], List[KitPurchaseOrder]]:
        """Simple greedy fallback."""
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
            
            passengers = flight.actual_passengers if flight.actual_passengers else flight.planned_passengers
            available = state.airport_inventories[flight.origin]
            
            kits = {}
            for cls in self.CLASS_KEYS:
                pax = passengers.get(cls, 0)
                if pax <= 0:
                    continue
                
                capacity = aircraft.kit_capacity.get(cls, 0)
                stock = available.get(cls, 0)
                to_load = min(pax, capacity, stock)
                
                if to_load > 0:
                    kits[cls] = to_load
            
            if kits:
                loads.append(KitLoadDecision(
                    flight_id=flight.flight_id,
                    kits_per_class=kits
                ))
        
        # Simple purchase logic
        purchases = []
        hub_inv = state.airport_inventories.get("HUB1", {})
        kits_to_buy = {}
        
        for cls in self.CLASS_KEYS:
            current = hub_inv.get(cls, 0)
            if current < 100:  # Simple threshold
                kits_to_buy[cls] = 200 - current
        
        if kits_to_buy:
            current_time = ReferenceHour(day=state.current_day, hour=state.current_hour)
            delivery_hours = now_hours + 24
            delivery_time = ReferenceHour(
                day=delivery_hours // 24,
                hour=delivery_hours % 24
            )
            purchases.append(KitPurchaseOrder(
                kits_per_class=kits_to_buy,
                order_time=current_time,
                expected_delivery=delivery_time
            ))
        
        return loads, purchases
