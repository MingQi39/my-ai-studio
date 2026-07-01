/**
 * Travel Agent settings API
 */

import { fetchTravelJSON } from './client';

export interface TravelSettings {
  max_rounds: number;
  amap_api_key: string;
  tavily_api_key: string;
  juhe_train_api_key: string;
  juhe_flight_api_key: string;
  tools_configured: boolean;
}

export interface TravelSettingsUpdate {
  max_rounds?: number;
}

export async function fetchTravelSettings(): Promise<TravelSettings> {
  return fetchTravelJSON<TravelSettings>('/travel/settings');
}

export async function updateTravelSettings(
  update: TravelSettingsUpdate,
): Promise<{ message: string }> {
  return fetchTravelJSON<{ message: string }>('/travel/settings', {
    method: 'POST',
    body: JSON.stringify(update),
  });
}
