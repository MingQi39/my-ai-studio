import { getApiBaseUrl, getJsonAuthHeaders } from '@/services/api';

export const SPIDER_API_BASE = `${getApiBaseUrl()}/spider`;

export function spiderHeaders(): Record<string, string> {
  return getJsonAuthHeaders();
}
