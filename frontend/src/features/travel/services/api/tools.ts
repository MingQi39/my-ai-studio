/**
 * Travel Agent tools API
 */

import { fetchTravelJSON, travelHeaders, TRAVEL_API_BASE } from './client';

export interface Tool {
  name: string;
  description: string;
  parameters: {
    type: string;
    properties: Record<string, unknown>;
    required: string[];
  };
}

export interface ToolTestResponse {
  ok: boolean;
  tool_name: string;
  result: unknown;
  error: string | null;
  duration_ms: number;
}

export async function fetchToolsList(): Promise<Tool[]> {
  return fetchTravelJSON<Tool[]>('/travel/tools/list');
}

export async function fetchToolInfo(toolName: string): Promise<Tool> {
  return fetchTravelJSON<Tool>(`/travel/tools/${toolName}`);
}

export async function testTool(
  toolName: string,
  args: Record<string, unknown>,
): Promise<ToolTestResponse> {
  const response = await fetch(`${TRAVEL_API_BASE}/travel/tools/${toolName}/test`, {
    method: 'POST',
    headers: travelHeaders(),
    body: JSON.stringify({ args }),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message =
      data?.error ||
      data?.detail?.error ||
      data?.detail ||
      `HTTP ${response.status}: ${response.statusText}`;
    throw new Error(String(message));
  }

  return data as ToolTestResponse;
}
