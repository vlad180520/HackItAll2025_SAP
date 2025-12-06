# Simplification Changes

## Overview
Refactored the solution strategy to be more modular, readable, and easier to debug.

## New Files Created

### `backend/solution/strategies/simple_lp_strategy.py` (389 lines)
**Purpose**: Clean, modular MILP optimization strategy

**Key Features**:
- **Modular Design**: Each major step is a separate method (~20-40 lines each)
- **Clear Flow**: `optimize()` → `_solve_milp()` → specific helper methods
- **Simple Fallback**: `_simple_greedy()` provides basic decisions if MILP unavailable

**Main Methods**:
```python
def optimize()                    # Main entry point
def _solve_milp()                 # MILP orchestration
def _get_loading_flights()        # Filter flights ready for loading
def _calculate_hub_demand()       # Calculate demand with fallback estimation
def _create_load_variables()      # Create load decision variables
def _create_purchase_variables()  # Create purchase variables with realistic bounds
def _add_demand_constraints()     # Ensure demand is covered
def _add_capacity_constraints()   # Enforce aircraft capacity
def _add_inventory_constraints()  # Track inventory flow
def _simple_greedy()              # Basic fallback heuristic
```

**Improvements Over Old Strategy**:
- 389 lines vs 816 lines (52% reduction)
- Separated concerns - each method has one clear purpose
- Better error messages with context
- Cleaner variable naming (no Hungarian notation)
- Fallback demand estimation: `10 flights/day × horizon × class_passengers`

### `frontend/src/components/StatsCounter.tsx` (50 lines)
**Purpose**: Real-time counter showing total decisions and purchases

**Features**:
- Two animated cards with icons (✈️ decisions, 📦 purchases)
- useMemo for efficient recalculation
- Updates every 2 seconds via polling
- Clean, minimal design

## Modified Files

### `backend/solution/decision_maker.py`
**Changes**:
- Switched from `RollingLPStrategy` to `SimpleLPStrategy`
- Simplified docstrings
- Updated both `__init__` and `update_config` methods

**Before**:
```python
from solution.strategies.rolling_lp_strategy import RollingLPStrategy
self.strategy = RollingLPStrategy(config=config, horizon_hours=72, solver_timeout_s=2)
```

**After**:
```python
from solution.strategies.simple_lp_strategy import SimpleLPStrategy
self.strategy = SimpleLPStrategy(config=config, horizon_hours=72, solver_timeout_s=2)
```

### `backend/simulation_runner.py`

#### `_get_visible_flights()` method (simplified from 40 lines to 22 lines)
**Changes**:
- Removed complex lookahead logic
- Clear filtering: skip LANDED, include only `current_hours <= scheduled_dep <= future_limit`
- Simple 7-day lookahead window

**Before**: Complex conditions, included past flights by mistake
**After**: Simple, clear logic that only includes future flights

#### Flight cleanup logic (simplified from 17 lines to 13 lines)
**Changes**:
- Triggers once per day (when `hour == 0`)
- Keeps last 48 hours of LANDED flights
- Single clear loop with timestamp comparison

### `backend/solution/strategies/__init__.py`
**Changes**:
- Added `SimpleLPStrategy` export alongside `RollingLPStrategy`
- Both strategies now available for testing/comparison

```python
__all__ = ["SimpleLPStrategy", "RollingLPStrategy"]
```

## Bug Fixes Included

### Bug 1: Flight Visibility Logic
**Problem**: `_get_visible_flights()` was including past flights
**Cause**: Condition `scheduled_dep_hours <= lookahead` allowed past flights
**Fix**: Changed to `current_hours <= scheduled_dep_hours <= lookahead`

### Bug 2: Demand Calculation Shrinking
**Problem**: Demand calculated only from loading_flights (shrinking list)
**Fix**: Calculate demand from ALL flights in horizon, not just loading flights
**Fallback**: Added demand estimation when no flights visible: `10 flights/day × horizon × passengers`

### Bug 3: Purchase Bounds Too Restrictive
**Problem**: Purchase upper bounds too low (100-500) when demand unclear
**Fix**: Increased to 1000+ with storage-based caps: `min(2 × storage, max(1000, demand × 1.5))`

## Testing Recommendations

1. **Monitor Logs**: Check that SimpleLPStrategy logs show:
   - "MILP solved optimally" messages
   - Non-zero purchase counts
   - Positive total decisions

2. **Watch StatsCounter**: Frontend counter should show:
   - Increasing total decisions
   - Increasing total purchases
   - No decrements after initial rounds

3. **Verify Feasibility**: 
   - Check simulation logs for "MILP infeasible" warnings
   - Should see consistent optimization success

4. **Compare Strategies**: 
   - Can temporarily switch back to RollingLPStrategy in decision_maker.py
   - Compare performance and readability

## Rollback Plan

If SimpleLPStrategy has issues:

1. Edit `backend/solution/decision_maker.py`:
   ```python
   from solution.strategies.rolling_lp_strategy import RollingLPStrategy
   self.strategy = RollingLPStrategy(config=config, horizon_hours=72, solver_timeout_s=2)
   ```

2. Both strategies remain in codebase for comparison

## Next Steps

1. **Test**: Run simulation and monitor behavior
2. **Validate**: Check that decisions/purchases increase properly
3. **Optimize**: Fine-tune parameters if needed (horizon, timeouts, bounds)
4. **Clean Up**: Remove old RollingLPStrategy once SimpleLPStrategy proven stable

## Key Principles Applied

- **Modularity**: Each method does one thing well
- **Readability**: Clear variable names, simple logic
- **Debuggability**: Separated concerns make it easy to isolate issues
- **Maintainability**: Less code, clearer structure, better comments
