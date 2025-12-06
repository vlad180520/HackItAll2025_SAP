# Genetic Algorithm Improvements - December 6, 2025

## Summary of Changes

### 1. **Purchase Logic Corrections** ✓
- **Problem**: Purchases calculated lead_time but didn't use it; bought kits that couldn't arrive in time
- **Solution**: 
  - Added `purchase_horizon_hours: int = 24` to `GeneticConfig`
  - `_compute_purchase_genes_simple()` now:
    - Calculates ETA = `now + lead_time + processing_time`
    - Only counts demand for flights AFTER purchase arrives (`eta_hours <= dep_hours < horizon_end`)
    - Only purchases if viable demand > 0
  - `_compute_purchase_genes_minimal()` uses similar logic with conservative 12h horizon
  - `_individual_to_purchase_orders()` now calculates `expected_delivery` using actual ETA from KIT_DEFINITIONS

### 2. **Penalties & Costs Aligned to Config** ✓
- **Added**: `OVER_CAPACITY` penalty for storage overflow
- **Using**: All penalties from `config.PENALTY_FACTORS`:
  - `UNFULFILLED_PASSENGERS`: 300 (progressive: 0.8×–1.5× based on shortage size)
  - `FLIGHT_OVERLOAD`: 2000 (0.5× for ≤2 overload, 1.0× for >2)
  - `NEGATIVE_INVENTORY`: 1000
  - `OVER_CAPACITY`: 500 (new - checks purchase arrival doesn't exceed storage)
- **Costs**: Using `KIT_DEFINITIONS` for:
  - Purchase cost per kit
  - Transport cost = `load_qty × weight × distance × fuel_cost_per_km`
  - Lead time for ETA calculation

### 3. **Inventory Timeline Tracking** ✓
- **Initial inventory**: Copied from `state.airport_inventories`
- **Purchases**: Added at `now + lead_time + processing_time` (HUB only)
- **Flight loads**: Deducted at departure, added to destination at `arrival + processing_time`
- **Negative inventory**: Penalized at every hour where stock < 0
- **Over-capacity**: Penalized when purchase arrival exceeds storage limit

### 4. **Horizon Management** ✓
- **Loading flights**: Evaluated in `[now, now + horizon_hours]` (default 6h)
- **Purchase planning**: Uses `purchase_horizon_hours` (default 24h)
- **ETA-aware**: Purchases only considered for flights they can actually serve

### 5. **Output Coherence** ✓
- **`expected_delivery`**: Now reflects actual `lead_time + processing_time`
  - Calculated per-class, uses max ETA across purchased classes
  - Converts to `ReferenceHour(day, hour)` correctly
- **Fitness and output**: Both use same ETA logic (consistent)

### 6. **Parameter Tuning**
Current `GeneticConfig` defaults:
```python
population_size: int = 80          # Increased diversity
num_generations: int = 60          # More evolution time
tournament_size: int = 5           # Stronger selection
crossover_rate: float = 0.80       # Balanced
mutation_rate: float = 0.20        # Adaptive exploration
elitism_count: int = 5             # Keep more best
horizon_hours: int = 6             # Loading flights lookahead
purchase_horizon_hours: int = 24   # Purchase planning window
no_improvement_limit: int = 15     # Early stopping patience
```

## Key Functions Modified

1. **`GeneticConfig`**: Added `purchase_horizon_hours`
2. **`_compute_purchase_genes_simple()`**: ETA-aware demand calculation
3. **`_compute_purchase_genes_minimal()`**: Conservative ETA-aware logic
4. **`_initialize_population()`**: Now receives `now_hours` parameter
5. **`_create_*_individual()`**: All receive `now_hours`, pass to purchase functions
6. **`_individual_to_purchase_orders()`**: Calculates `expected_delivery` from KIT_DEFINITIONS
7. **`_evaluate_fitness()`**: Added OVER_CAPACITY penalty, improved inventory timeline

## Testing

```bash
cd /home/utzu/HackItAll2025_SAP/backend
source .venv/bin/activate
python3 -c "from solution.strategies.genetic_strategy import GeneticStrategy, GeneticConfig; print('✓ Import successful')"
```

**Result**: ✓ Imports successfully, no syntax errors

## Expected Improvements

1. **Smarter purchases**: Won't buy kits that can't arrive in time
2. **Better inventory management**: Timeline tracking prevents over-purchasing
3. **More realistic costs**: All penalties/costs from config, consistent with evaluation platform
4. **Strategic decisions**: Longer purchase horizon (24h) allows proactive planning
5. **Storage respect**: Won't overflow HUB capacity

## Performance Metrics to Monitor

- Total cost reduction (target: < 750M → < 500M)
- Unfulfilled passenger penalties (should decrease significantly)
- Negative inventory penalties (should be minimal/zero)
- Purchase timing effectiveness (kits arrive before needed flights)

## Next Steps (Optional)

1. **Adaptive mutation**: Decrease mutation_rate as generations progress
2. **Multi-objective fitness**: Separate operational cost from penalties
3. **Demand forecasting**: Use historical patterns for better purchase decisions
4. **Hub-spoke optimization**: Prioritize HUB inventory levels differently
