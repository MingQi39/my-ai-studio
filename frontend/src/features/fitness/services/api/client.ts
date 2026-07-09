import { getApiBaseUrl, getJsonAuthHeaders } from '@/services/api';

export const FITNESS_API_BASE = `${getApiBaseUrl()}/fitness`;

export function fitnessHeaders(): Record<string, string> {
  return getJsonAuthHeaders();
}

