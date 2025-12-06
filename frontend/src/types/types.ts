/** TypeScript interfaces matching backend pydantic models */

export interface ReferenceHour {
  day: number;
  hour: number;
}

export interface Airport {
  code: string;
  name: string;
  is_hub: boolean;
  storage_capacity: Record<string, number>;
  loading_costs: Record<string, number>;
  processing_costs: Record<string, number>;
  processing_times: Record<string, number>;
  current_inventory?: Record<string, number>;
}

export interface AircraftType {
  type_code: string;
  passenger_capacity: Record<string, number>;
  kit_capacity: Record<string, number>;
  fuel_cost_per_km: number;
}

export interface Flight {
  flight_id: string;
  flight_number: string;
  origin: string;
  destination: string;
  scheduled_departure: ReferenceHour;
  scheduled_arrival: ReferenceHour;
  planned_passengers: Record<string, number>;
  planned_distance: number;
  aircraft_type: string;
  actual_departure?: ReferenceHour;
  actual_arrival?: ReferenceHour;
  actual_passengers?: Record<string, number>;
  actual_distance?: number;
  event_type: string;
}

export interface KitLoadDecision {
  flight_id: string;
  kits_per_class: Record<string, number>;
}

export interface KitPurchaseOrder {
  kits_per_class: Record<string, number>;
  order_time: ReferenceHour;
  expected_delivery: ReferenceHour;
}

export interface KitMovement {
  movement_type: string;
  airport: string;
  kits_per_class: Record<string, number>;
  execute_time: ReferenceHour;
}

export interface PenaltyRecord {
  code: string;
  cost: number;
  reason: string;
  issued_time: ReferenceHour;
}

export interface GameState {
  current_day: number;
  current_hour: number;
  airport_inventories: Record<string, Record<string, number>>;
  in_process_kits: Record<string, KitMovement[]>;
  pending_movements: KitMovement[];
  total_cost: number;
  penalty_log: PenaltyRecord[];
  flight_history: Flight[];
}

export interface StatusResponse {
  status: string;
  round: number;
  costs: number | Record<string, number>;
  penalties: PenaltyRecord[];
}

export interface InventoryResponse {
  inventories: Record<string, Record<string, number>>;
}

export interface HistoryResponse {
  decision_log: Array<{
    round: number;
    time: ReferenceHour;
    decisions: number;
    purchases: number;
    rationale: string;
  }>;
  cost_log: Array<{
    round: number;
    costs: Record<string, number>;
    penalties: PenaltyRecord[];
    api_total_cost?: number;
  }>;
  total_rounds: number;
}

