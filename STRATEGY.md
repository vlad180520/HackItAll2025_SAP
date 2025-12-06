# Analiza Provocării Rotables - HackITAll 2025

## 📊 REZUMAT PROVOCARE

**Obiectiv**: Minimizați costul total pentru gestionarea kit-urilor (rotables) pe o rețea hub-and-spoke de aeroporturi pe parcursul a 720 de runde (30 zile × 24 ore).

**Cost Total = Costuri Operaționale + Penalități**

---

## 📥 DATE DE INTRARE (Ce primim)

### 1. **Date Statice din CSV-uri** (la început)

#### `aircraft_types.csv`
- `type_code`: Tip avion (ex: "OJF294")
- `first_class_seats`, `business_seats`, `premium_economy_seats`, `economy_seats`: Capacitate pasageri
- `cost_per_kg_per_km`: Cost combustibil
- `first_class_kits_capacity`, `business_kits_capacity`, etc.: **Capacitate kituri per clasă**

#### `airports_with_stocks.csv`
- `code`: Cod aeroport (ex: "HUB1", "ZHVK")
- `name`: Nume
- `*_processing_time`: Timp procesare per clasă (ore)
- `*_processing_cost`: Cost procesare per kit
- `*_loading_cost`: Cost încărcare per kit
- `initial_*_stock`: Stocuri inițiale per clasă
- `capacity_*`: **Capacitate stocare maximă per clasă**

#### `flight_plan.csv`
- `depart_code`, `arrival_code`: Ruta (HUB1 ↔ outstation)
- `scheduled_hour`, `scheduled_arrival_hour`: Timpi planificați
- `distance_km`: Distanță
- `Mon`, `Tue`, ..., `Sun`: Zile când zboară (0/1)

### 2. **Date Dinamice din API** (fiecare rundă)

#### Response de la API (`HourResponseDto`):
```json
{
  "day": 5,
  "hour": 12,
  "flightUpdates": [
    {
      "eventType": "SCHEDULED",  // sau CHECKED_IN, LANDED
      "flightNumber": "LH123",
      "flightId": "uuid-here",
      "originAirport": "HUB1",
      "destinationAirport": "A1",
      "departure": {"day": 5, "hour": 14},
      "arrival": {"day": 5, "hour": 16},
      "passengers": {
        "first": 2,
        "business": 10,
        "premiumEconomy": 20,
        "economy": 100
      },
      "aircraftType": "A320",
      "distance": 3500.0
    }
  ],
  "penalties": [...],
  "totalCost": 12345.67
}
```

**Tipuri de Evenimente**:
- **SCHEDULED** (24h înainte): Date planificate - passengers, scheduled times
- **CHECKED_IN** (1h înainte): Date actuale - actual departure, actual passengers
- **LANDED** (la sosire): Actual arrival, actual distance

---

## 📤 CE TREBUIE SĂ TRIMITEM (Fiecare rundă)

### Request către API (`HourRequestDto`):
```json
{
  "day": 5,
  "hour": 12,
  "flightLoads": [
    {
      "flightId": "uuid-zbor-1",
      "loadedKits": {
        "first": 2,
        "business": 10,
        "premiumEconomy": 20,
        "economy": 100
      }
    },
    {
      "flightId": "uuid-zbor-2",
      "loadedKits": {
        "first": 0,
        "business": 5,
        "premiumEconomy": 10,
        "economy": 50
      }
    }
  ],
  "kitPurchasingOrders": {
    "first": 10,
    "business": 50,
    "premiumEconomy": 30,
    "economy": 200
  }
}
```

**Detalii**:
- `flightLoads`: Lista cu încărcări pentru zborurile care **PLEACĂ în următoarele 24h**
- `kitPurchasingOrders`: **DOAR la HUB1** - comenzi noi (cu lead-time!)

---

## 💰 STRUCTURA COSTURILOR

### Costuri Operaționale (pe zbor):
1. **Loading Cost**: `Σ (kits × loadingCost_airport_class)`
2. **Movement Cost**: `distance × fuelCost/kg/km × Σ (kits × weight_class)`
3. **Processing Cost**: `Σ (kits × processingCost_airport_class)`
4. **Purchasing Cost**: `Σ (kits × cost_class)` (doar la HUB1)

### Penalități (FOARTE SCUMPE):
1. **Understock** (inventar < 0): `NEGATIVE_INVENTORY_FACTOR × |negativeKits|`
2. **Overstock** (> capacitate): `OVER_CAPACITY_FACTOR × exceededKits`
3. **Plane Overload** (> capacitate avion): `FLIGHT_OVERLOAD_FACTOR × distance × fuelCost × Σ(kitCost × excess)`
4. **Unfulfilled Passengers** (pasageri fără kit): `UNFULFILLED_PASSENGERS_FACTOR × distance × Σ(kitCost × missing)`
5. **Invalid Flight**: `INCORRECT_FLIGHT_LOAD_FACTOR` per referință invalidă

**End-Game Penalties** (la final):
- Stocuri rămase, kituri în procesare, zboruri neacoperite
- **EARLY STOP**: ×10 dacă opriți în ultimele 24h!

---

## 🚀 SOLUȚIE SIMPLĂ - STRATEGIA GREEDY SAFE

### Principii:
1. **EVITĂ PENALITĂȚI CU ORICE PREȚ** - sunt mult mai scumpe decât costurile operaționale
2. **Buffer de siguranță** - întotdeauna încarcă puțin mai mult
3. **Planificare 24h în avans** - folosește datele SCHEDULED
4. **Reaprovizionare predictivă** - cumpără la HUB1 înainte să se termine stocul

### Algoritm Simplu (per rundă):

```python
def play_round(current_day, current_hour, flight_updates):
    decisions = []
    purchases = {"FIRST": 0, "BUSINESS": 0, "PREMIUM_ECONOMY": 0, "ECONOMY": 0}
    
    # 1. Procesează zborurile SCHEDULED și CHECKED_IN (care pleacă în 24h)
    for flight in flight_updates:
        if flight.eventType in ["SCHEDULED", "CHECKED_IN"]:
            # Verifică dacă pleacă de la un aeroport unde avem stoc
            origin_stock = get_current_stock(flight.originAirport)
            
            # Pentru fiecare clasă, încarcă: pasageri + 10% buffer
            kits_to_load = {}
            for class_type in ["FIRST", "BUSINESS", "PREMIUM_ECONOMY", "ECONOMY"]:
                passengers = flight.passengers[class_type]
                buffer = int(passengers * 0.1) + 2  # 10% + minim 2
                needed = passengers + buffer
                
                # Nu depăși capacitatea avionului
                aircraft = get_aircraft_type(flight.aircraftType)
                capacity = aircraft.kits_capacity[class_type]
                kits_to_load[class_type] = min(needed, capacity)
            
            decisions.append({
                "flight_id": flight.flightId,
                "kits_per_class": kits_to_load
            })
    
    # 2. Verifică stocurile la HUB1 și reaprovizionează dacă < 30% din capacitate
    hub_stock = get_current_stock("HUB1")
    hub_capacity = get_airport_capacity("HUB1")
    
    for class_type in ["FIRST", "BUSINESS", "PREMIUM_ECONOMY", "ECONOMY"]:
        current = hub_stock[class_type]
        capacity = hub_capacity[class_type]
        threshold = capacity * 0.3  # Reaprovizionează sub 30%
        
        if current < threshold:
            # Comandă pentru a ajunge la 80% din capacitate
            target = int(capacity * 0.8)
            purchases[class_type] = max(0, target - current)
    
    return decisions, purchases
```

### Optimizări Posibile:

#### **Nivel 1 - Îmbunătățiri Simple**:
- Ajustează buffer-ul dinamic bazat pe istoricul întârzierilor
- Predicție cerere: analizează pattern-uri zilnice/săptămânale
- Prioritizare: încarcă mai întâi zborurile lungi (mai profitabile)

#### **Nivel 2 - Optimizare Medie**:
- **Demand Forecasting**: Machine Learning pentru predicția pasagerilor actuali
- **Stock Rebalancing**: Dacă un outstation are prea multe kituri, trimite înapoi la HUB
- **Dynamic Safety Stock**: Calcul matematic pentru nivelul optim de siguranță

#### **Nivel 3 - Optimizare Avansată**:
- **Linear Programming**: Modelează ca problemă de optimizare cu constrângeri
- **Genetic Algorithm**: Evoluție de soluții pentru minimizare cost global
- **Reinforcement Learning**: Agent care învață politica optimă din simulări

---

## 📋 CHECKLIST IMPLEMENTARE

### Faza 1 - Setup (1-2 ore):
- [ ] Parsează CSV-urile și construiește structuri de date
- [ ] Implementează API client (start session, play round, stop session)
- [ ] Testează conectivitatea și flow-ul basic

### Faza 2 - Algoritm Greedy (2-3 ore):
- [ ] Implementează logica de încărcare zboruri (pasageri + buffer)
- [ ] Implementează logica de reaprovizionare HUB1
- [ ] Tracking stocuri per aeroport în memorie
- [ ] Validare: nu depăși capacități avion/aeroport

### Faza 3 - Optimizări (3-4 ore):
- [ ] Ajustare buffer dinamic
- [ ] Predicție demand bazată pe istoric
- [ ] Fine-tuning parametri (threshold reaprovizionare, buffer %)
- [ ] Logging detaliat pentru debugging

### Faza 4 - Testing & Tuning (2-3 ore):
- [ ] Rulează simulări complete (720 runde)
- [ ] Analizează penalitățile primite
- [ ] Ajustează strategia pentru a elimina penalități
- [ ] Optimizează pentru cost minim

---

## 🎯 METRICI DE SUCCES

1. **Zero Penalități pentru Unfulfilled Passengers** - Prioritate #1
2. **Zero Penalități pentru Plane Overload** - Verifică capacitatea
3. **Minimal Understock** - Buffer adecvat
4. **Overstock Acceptabil** - Mai bine prea mult decât prea puțin
5. **Cost Operațional Optimizat** - După ce penalitățile sunt eliminate

---

## 💡 SFATURI CHEIE

1. **Simplitate**: Începe cu algoritm foarte simplu care funcționează
2. **Logging**: Logează TOTUL - fiecare decizie, stoc, cost
3. **Validare**: Verifică limitele ÎNAINTE de a trimite la API
4. **Iterare Rapidă**: Rulează, analizează, ajustează, repeat
5. **Focus pe Penalități**: Elimină penalitățile înainte de optimizare costuri

**REMEMBER**: Nu trebuie să fie perfect, trebuie să fie mai bun decât competiția! 🏆
