# Solution Module

Acest folder conține toată logica specifică pentru rezolvarea problemei de optimizare a kit-urilor.

## Structură

```
solution/
├── __init__.py                 # Package initialization
├── README.md                   # Această documentație
├── config.py                   # Configurări specifice soluției (MODIFICĂ AICI)
├── decision_maker.py          # Orchestrator principal
└── strategies/                 # Implementări de strategii
    ├── __init__.py
    └── greedy_strategy.py     # Strategia greedy (MODIFICĂ AICI)
```

## Cum să modifici soluția

### 1. Schimbă parametrii (CEL MAI RAPID)

Editează `config.py`:

```python
SAFETY_BUFFER = 10           # Crește buffer-ul de siguranță
REORDER_THRESHOLD = 0.4      # Cumpără mai devreme  
TARGET_STOCK_LEVEL = 60      # Target mai mare
LOOKAHEAD_HOURS = 48         # Planifică mai departe
DEMAND_MULTIPLIER = 1.3      # Safety margin mai mare
```

Profile predefinite:
- `SolutionConfig.default()` - Echilibrat
- `SolutionConfig.conservative()` - Siguranță maximă
- `SolutionConfig.aggressive()` - Costuri minime

### 2. Modifică logica de purchase

Editează `strategies/greedy_strategy.py` → clasa `GreedyPurchaseStrategy`:

```python
def decide_purchases(self, state, flights, airports):
    # MODIFICĂ AICI logica de cumpărare
    # Exemplu: cumpără mai mult pentru business class
    if class_type == "business":
        needed = needed * 1.5  # 50% mai mult
```

### 3. Modifică logica de loading

Editează `strategies/greedy_strategy.py` → clasa `GreedyLoadingStrategy`:

```python
def decide_loading(self, state, flights, airports, aircraft_types):
    # MODIFICĂ AICI logica de încărcare
    # Exemplu: prioritizează clasele premium
```

## Integrare cu Backend

Folosește `SolutionOptimizer` în loc de `GreedyOptimizer`:

```python
from solution_optimizer import SolutionOptimizer

optimizer = SolutionOptimizer(config)
loads, purchases, rationale = optimizer.decide(state, flights, airports, aircraft)
```

## Fișiere Principale

- **config.py** - Toți parametrii configurabili
- **strategies/greedy_strategy.py** - Logica principală de decizie
- **decision_maker.py** - Coordonează execuția
- **solution_optimizer.py** (în backend/) - Wrapper pentru integrare
