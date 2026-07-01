export interface PlanLocation {
  name: string;
  address?: string | null;
  note?: string | null;
}

export interface PlanActivity {
  time?: string | null;
  title: string;
  description?: string | null;
  location?: PlanLocation | null;
}

export interface PlanDay {
  day: number;
  title?: string | null;
  activities: PlanActivity[];
}

export interface PlanBudgetItem {
  category: string;
  amount?: number | null;
  currency?: string;
  note?: string | null;
}

export interface StructuredTravelPlan {
  title: string;
  destination: string;
  duration_days?: number | null;
  travel_dates?: string | null;
  budget_total?: number | null;
  budget_currency?: string;
  summary: string;
  weather_summary?: string | null;
  daily_itinerary: PlanDay[];
  accommodations: PlanLocation[];
  transport: string[];
  budget_breakdown: PlanBudgetItem[];
  tips: string[];
  data_verified: boolean;
}

export interface TravelPlanGenerateResponse {
  plan: StructuredTravelPlan;
  markdown: string;
  fingerprint?: string | null;
  exists?: boolean;
  is_stale?: boolean;
  generated_at?: string | null;
}

export interface TravelPlanStatusResponse {
  exists: boolean;
  is_stale?: boolean;
  fingerprint?: string | null;
  generated_at?: string | null;
  plan?: StructuredTravelPlan | null;
  markdown?: string | null;
}

export interface ToolEvidenceItem {
  tool_name: string;
  result: string;
}

export interface TravelPlanGenerateRequest {
  model_config_id: string;
  session_id?: string | null;
  user_request?: string | null;
  assistant_plan?: string | null;
  tool_evidence?: ToolEvidenceItem[];
  data_verified?: boolean;
}
