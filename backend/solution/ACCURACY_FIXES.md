# Accuracy Fixes and Strategy Updates

This document tracks changes made to improve accuracy and reduce penalties/costs.

## Latest Updates

### Purchase Logic Simplification

- **Buy-when-needed logic**: Purchases are now computed based on projected demand within the horizon, without comparing "min(buying vs penalty)".
- Algorithm:
  1. For each class at HUB, compute demand from flights departing within `purchase_horizon_hours` (60h default)
  2. Only count flights where departure >= ETA (lead_time + processing_time)
  3. Target = demand * buffer (1.05 = 5% buffer for standard, 1.02 = 2% for minimal)
  4. Purchase = min(target - stock, capacity - stock)
  5. If stock >= target, purchase = 0
- Horizon and buffer are configurable in `GeneticConfig`
- Minimal variant uses shorter horizon (36h) and smaller buffer (2%)

### Initializer Passenger Bias

- All population initializers (conservative, aggressive, random) now bias to at least passenger coverage
- **Conservative**: Loads exactly passengers (no buffer)
- **Aggressive**: Loads passengers * buffer (5-10% depending on class)
- **Random**: Samples between passengers (100%) and passengers * 1.10 (110%)
- Flights are processed chronologically, applying arrivals before departures

### Greedy Anchor Injection

- A deterministic greedy baseline is injected into the population each generation
- Greedy anchor:
  - Loads passengers with 5-8% buffer (class-dependent)
  - Clamps to availability/capacity
  - Processes flights chronologically
  - Uses the updated `compute_purchase_genes_simple` for buy-when-needed purchases
- This provides stability and prevents genetic drift away from good solutions

### Old Strategies Removed

- `simple_lp_strategy.py` - Deleted
- `rolling_lp_strategy.py` - Deleted
- Only the genetic strategy remains under `backend/solution/strategies/`

## Modular Structure

The genetic algorithm is now organized into separate modules under `backend/solution/strategies/genetic/`:

| Module | Description | LOC |
|--------|-------------|-----|
| `config.py` | GeneticConfig class, TRANSPORT_COST_SCALE | ~50 |
| `types.py` | Individual class | ~40 |
| `precompute.py` | Helper functions for data preparation | ~80 |
| `initialization.py` | Population initialization (conservative, aggressive, random, greedy) | ~200 |
| `purchases.py` | Purchase computation (buy-when-needed logic) | ~180 |
| `repair.py` | Feasibility repair functions | ~70 |
| `operators.py` | Selection, crossover, mutation | ~130 |
| `fitness.py` | Fitness evaluation with timeline tracking | ~200 |
| `strategy.py` | Main GeneticStrategy class | ~230 |

All files are under 500 LOC as required.

## Configuration Constants

- `TRANSPORT_COST_SCALE = 0.0005` (in `genetic/config.py`)
- `purchase_horizon_hours = 60` (60-hour purchase planning horizon)
- `horizon_hours = 4` (4-hour tactical loading horizon)
- `purchase_buffer = 1.05` (5% buffer for standard purchases)
- `purchase_buffer_minimal = 1.02` (2% buffer for minimal variant)
- `minimal_horizon_hours = 36` (shorter horizon for minimal purchases)

## Penalty Formulas

Penalty formulas in `genetic/fitness.py` remain unchanged:
- Progressive unfulfilled passenger penalty (0.8x for <=2, 1.0x for 3-5, 1.5x for >5)
- Reduced overload penalty for small violations (0.5x for <=2)
- Standard penalties for negative inventory and over-capacity

## Imports

The wrapper `genetic_strategy.py` exports:
- `GeneticStrategy` - Main strategy class
- `GeneticConfig` - Configuration dataclass
- `Individual` - Solution chromosome
- `TRANSPORT_COST_SCALE` - Transport cost scaling factor

