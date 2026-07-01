/**
 * Travel feature HTTP client — uses main studio auth + /api/v1 base URL.
 */

import { getApiBaseUrl, getJsonAuthHeaders, getToken } from '@/services/api';

export const TRAVEL_API_BASE = getApiBaseUrl();

export function travelHeaders(): Record<string, string> {
  return getJsonAuthHeaders();
}

export async function fetchTravelJSON<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${TRAVEL_API_BASE}${endpoint}`, {
    ...options,
    headers: {
      ...travelHeaders(),
      ...options?.headers,
    },
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = data.detail || data.message || detail;
    } catch {
      // ignore
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }

  return response.json();
}

export async function fetchTravelBlob(endpoint: string, options?: RequestInit): Promise<Blob> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${TRAVEL_API_BASE}${endpoint}`, {
    ...options,
    headers: {
      ...headers,
      ...options?.headers,
    },
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = data.detail || data.message || detail;
    } catch {
      // ignore
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }

  return response.blob();
}

export function downloadBlobFile(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
