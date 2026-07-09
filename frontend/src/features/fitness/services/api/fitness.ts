import { fitnessHeaders, FITNESS_API_BASE } from './client';

export interface FitnessTodaySummaryResponse {
  date: string;
  daily_calorie_goal: number;
  consumed_kcal: number;
  remaining_kcal: number;
  entries: Array<{
    id: string;
    meal_type: string;
    items: Array<{ name: string; qty: number; unit: string; kcal: number; source: string }>;
    total_kcal: number;
    note?: string | null;
    session_id?: string | null;
  }>;
  disclaimer: string;
}

export async function fetchFitnessTodaySummary(timezone?: string | null): Promise<FitnessTodaySummaryResponse> {
  const params = new URLSearchParams();
  if (timezone) params.append('timezone', timezone);

  const url = `${FITNESS_API_BASE}/diary/today${params.toString() ? `?${params.toString()}` : ''}`;
  const res = await fetch(url, { headers: fitnessHeaders() });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function updateDailyCalorieGoal(daily_calorie_goal: number): Promise<FitnessTodaySummaryResponse> {
  const url = `${FITNESS_API_BASE}/goals`;
  const res = await fetch(url, {
    method: 'PUT',
    headers: {
      ...fitnessHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ daily_calorie_goal }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `HTTP ${res.status}`);
  }
  // backend returns FitnessGoalResponse; callers can refetch today summary
  return (await res.json()) as any;
}

export async function deleteFitnessDiaryEntry(entry_id: string): Promise<void> {
  const url = `${FITNESS_API_BASE}/diary/${encodeURIComponent(entry_id)}`;
  const res = await fetch(url, { method: 'DELETE', headers: fitnessHeaders() });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `HTTP ${res.status}`);
  }
}

export interface FitnessAgentApproveResponse {
  ok: boolean;
  tool_name: string;
  result: Record<string, unknown> | null;
  message: string;
}

export async function approveFitnessAgentAction(payload: {
  session_id?: string | null;
  tool_name: string;
  tool_args: Record<string, unknown>;
  call_id?: string;
  timezone?: string | null;
}): Promise<FitnessAgentApproveResponse> {
  const res = await fetch(`${FITNESS_API_BASE}/agent/approve`, {
    method: 'POST',
    headers: {
      ...fitnessHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      session_id: payload.session_id ?? null,
      tool_name: payload.tool_name,
      tool_args: payload.tool_args,
      call_id: payload.call_id ?? null,
      timezone: payload.timezone ?? null,
    }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return res.json();
}

