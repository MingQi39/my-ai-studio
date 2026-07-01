import { downloadBlobFile, fetchTravelBlob, fetchTravelJSON } from '@/features/travel/services/api/client';
import type {
  TravelPlanGenerateRequest,
  TravelPlanGenerateResponse,
  TravelPlanStatusResponse,
} from '@/features/travel/types/itinerary';
import { sanitizeFilename } from '@/features/travel/utils/exportPlan';

export async function generateStructuredPlan(
  payload: TravelPlanGenerateRequest,
): Promise<TravelPlanGenerateResponse> {
  return fetchTravelJSON<TravelPlanGenerateResponse>('/travel/plan/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchFormalPlanStatus(sessionId: string): Promise<TravelPlanStatusResponse> {
  return fetchTravelJSON<TravelPlanStatusResponse>(`/travel/plan/session/${sessionId}`);
}

export async function downloadFormalPlanPdf(sessionId: string, title: string): Promise<void> {
  const blob = await fetchTravelBlob(`/travel/plan/session/${sessionId}/pdf`);
  downloadBlobFile(blob, `${sanitizeFilename(title)}.pdf`);
}
