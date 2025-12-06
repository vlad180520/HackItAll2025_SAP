# Rolling-Horizon LP Strategy - Algorithm Documentation

## Overview

The `RollingLPStrategy` implements a **general-purpose optimization algorithm** that works with any input data provided through the game state and API responses. It does NOT rely on hardcoded CSV files.

## Algorithm Description

### 1. Input Data (Generic)

The algorithm receives:
- **GameState**: Current inventories, costs, penalties
- **Flights**: List of scheduled flights with passengers, origin, destination
- **Airports**: Dictionary with processing times, costs, capacities (from API/data loader)
- **Aircraft Types**: Kit capacities per class (from API/data loader)

All data comes from **runtime parameters**, not hardcoded files.

### 2. Optimization Approach

**Rolling Horizon**: 
- Looks ahead 36-48 hours into the future
- Makes decisions for the current hour only
- Re-optimizes every hour with updated data

**Linear Programming Formulation**:

**Decision Variables**:
- `load[flight, class]`: Number of kits to load on each flight
- `purchase[hour, class]`: Number of kits to purchase at HUB (for future delivery)
- `slack[flight, class]`: Unmet passenger demand (soft constraint)

**Objective Function** (Minimize):
```
Cost = Σ (1000 × slack)                    # Heavy penalty for unmet demand
     + Σ (loading_cost × load)             # Loading costs from airport data
     + Σ (kit_cost × purchase)             # Purchase costs
     + Σ (processing_cost × load)          # Processing costs from airport data
```

**Constraints**:

1. **Demand Coverage** (soft):
   ```
   load[flight, class] + slack[flight, class] >= passengers[flight, class]
   ```
   - At outstations: Add 5% buffer for contingency
   - At HUB: Exact demand (no buffer)

2. **Inventory Balance** (per airport, per class):
   ```
   initial_inventory + Σ arrivals + Σ purchases >= Σ departures
   ```
   - Arrivals are only available after `processing_time` hours
   - Uses **actual processing times from airport data**

3. **Aircraft Capacity**:
   ```
   load[flight, class] <= aircraft.kit_capacity[class]
   ```
   - Uses actual capacities from aircraft data

4. **Non-negativity**:
   ```
   load, purchase, slack >= 0
   ```

### 3. Key Features

**Adaptive Processing Times**:
- Uses `airport.processing_times[class]` from data
- Example: HUB1 has 6h for FIRST, outstations have 45h
- Algorithm automatically adjusts arrival availability

**Cost-Aware**:
- Uses `airport.loading_costs[class]` from data
- Uses `airport.processing_costs[class]` from data
- Balances between loading more vs. accepting penalties

**Capacity-Aware**:
- Respects `airport.storage_capacity[class]` limits
- Respects `aircraft.kit_capacity[class]` limits

**Fallback Heuristic**:
- If LP solver fails or unavailable: greedy heuristic
- Loads exact demand at HUB, demand + 5% buffer at outstations
- Pre-positions kits for return flights when possible

### 4. Decision Logic

**At HUB Airports**:
- Load exact passenger count (no buffer)
- Consider pre-positioning kits for return flights
- Purchase kits if inventory < 105% of horizon demand

**At Outstation Airports**:
- Load passenger count + 5% buffer
- Account for long processing times (kits may not return in time)
- Rely more on initial inventory

### 5. Solver Configuration

- **Solver**: CBC (COIN-OR Branch and Cut)
- **Timeout**: 2-5 seconds per optimization
- **Objective**: Minimize total cost
- **Status**: Returns optimal, infeasible, or timeout

## Generality Guarantees

✅ **No Hardcoded Data**:
- All parameters come from function arguments
- No CSV file paths in the algorithm
- No assumptions about specific airports or aircraft

✅ **Data-Driven**:
- Processing times: `airport.processing_times[class]`
- Costs: `airport.loading_costs[class]`, `airport.processing_costs[class]`
- Capacities: `aircraft.kit_capacity[class]`, `airport.storage_capacity[class]`

✅ **Configurable**:
- Horizon length: 24-72 hours
- Solver timeout: 1-10 seconds
- Buffer percentages: 5% at outstations

✅ **Robust**:
- Handles missing data with sensible defaults
- Falls back to heuristic if solver fails
- Validates decisions before returning

## Usage Example

```python
# Generic usage - works with any data
strategy = RollingLPStrategy(config=config, horizon_hours=48)

loads, purchases = strategy.optimize(
    state=current_game_state,        # From API
    flights=upcoming_flights,        # From API
    airports=airports_dict,          # From data loader
    aircraft_types=aircraft_dict     # From data loader
)
```

The algorithm will automatically use the processing times, costs, and capacities from the provided data.
