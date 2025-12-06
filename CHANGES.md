# Changelog - Algorithm Generalization & Cost Formatting

## Summary

Implementat algoritm general de optimizare (nu dependent de CSV-uri specifice) și formatare europeană pentru costuri.

## Changes

### 1. Cost Formatting (European Format)

**New File**: `backend/utils.py`
- Funcție `format_cost(cost: float) -> str`
- Convertește `12345.67` → `12.345,67`
- Separator mii: `.` (punct)
- Separator zecimale: `,` (virgulă)

**Updated Files**:
- `backend/services/simulation_service.py`
  - Import `format_cost`
  - `get_status()` returnează `costs_formatted` (string formatat)
  - Păstrează `costs` numeric pentru calcule
  
- `backend/logger.py`
  - Import `format_cost`
  - Formatare în text summary: `Total Cost: 12.345,67`
  
- `backend/schemas/status_schemas.py`
  - Adăugat `costs_formatted: Optional[str]` în `StatusResponse`
  
- `frontend/src/types/types.ts`
  - Adăugat `costs_formatted?: string` în `StatusResponse`
  
- `frontend/src/components/Dashboard.tsx`
  - Folosește `costs_formatted` dacă e disponibil
  - Fallback la formatare locală dacă nu

### 2. Algorithm Generalization

**Documentation**: `backend/solution/ALGORITHM.md`
- Documentație completă a algoritmului
- Demonstrează că e **data-driven**, nu hardcoded
- Toate datele vin din parametri runtime

**Key Points**:

✅ **Algorithm is Generic**:
```python
# Receives data as parameters
loads, purchases = strategy.optimize(
    state=current_game_state,     # Runtime data
    flights=upcoming_flights,     # Runtime data
    airports=airports_dict,       # Runtime data (from API/loader)
    aircraft_types=aircraft_dict  # Runtime data (from API/loader)
)
```

✅ **Uses Runtime Data**:
- `airport.processing_times[class]` - from data (HUB: 6h, outstations: 45h)
- `airport.loading_costs[class]` - from data
- `airport.processing_costs[class]` - from data
- `aircraft.kit_capacity[class]` - from data
- `airport.storage_capacity[class]` - from data

✅ **No Hardcoded Assumptions**:
- No CSV file paths in algorithm
- No assumptions about specific airports
- DEFAULT_* values only as fallbacks

✅ **Optimization Logic**:
- **Rolling Horizon**: 36-48h lookahead
- **Linear Programming**: Min-cost flow formulation
- **Objective**: Minimize (penalties + loading costs + processing costs + purchase costs)
- **Constraints**:
  1. Demand coverage (with slack for soft constraint)
  2. Inventory balance (respects processing times)
  3. Aircraft capacity limits
  4. Non-negativity

✅ **Adaptive Behavior**:
- At HUB: Load exact demand (fast processing)
- At Outstations: Add 5% buffer (long processing, uncertain returns)
- Accounts for actual processing times from data

## Testing

### Cost Formatting
```
✅ 12345.67 → 12.345,67
✅ 1234567.89 → 1.234.567,89
✅ 123.45 → 123,45
✅ 1000000.00 → 1.000.000,00
```

### Algorithm Validation
```
✅ HUB1 → ZHVK: Loads exact passenger count (5/20/15/100)
✅ ZHVK → HUB1: Adds 5% buffer (5/16/13/84 for 4/15/12/80 pax)
✅ Uses real processing times (ZHVK: 45h for FIRST)
✅ Produces optimal LP solution (cost=871.69)
```

## API Response Example

**Before**:
```json
{
  "status": "running",
  "round": 10,
  "costs": 12345.67,
  "penalties": []
}
```

**After**:
```json
{
  "status": "running",
  "round": 10,
  "costs": 12345.67,
  "costs_formatted": "12.345,67",
  "penalties": []
}
```

Frontend poate folosi `costs_formatted` pentru display lizibil.

## Files Modified

### Backend
- ✅ `backend/utils.py` (NEW)
- ✅ `backend/services/simulation_service.py`
- ✅ `backend/logger.py`
- ✅ `backend/schemas/status_schemas.py`
- ✅ `backend/solution/ALGORITHM.md` (NEW)

### Frontend
- ✅ `frontend/src/types/types.ts`
- ✅ `frontend/src/components/Dashboard.tsx`

## Backward Compatibility

✅ **Fully Backward Compatible**:
- `costs` numeric field still present
- `costs_formatted` is optional
- Old clients ignore new field
- New clients prefer formatted field
