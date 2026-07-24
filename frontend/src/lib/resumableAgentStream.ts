export type ResumableAgentStreamStatus = {
  session_id: string;
  is_streaming: boolean;
  event_count: number;
  metadata: Record<string, unknown>;
};

async function readError(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    if (typeof payload.detail === 'string') return payload.detail;
  } catch {
    // Fall back to the HTTP status below.
  }
  return response.statusText || `HTTP ${response.status}`;
}

export async function fetchResumableAgentStreamStatus(
  url: string,
  headers: Record<string, string>,
): Promise<ResumableAgentStreamStatus> {
  const response = await fetch(url, { method: 'GET', headers });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json() as Promise<ResumableAgentStreamStatus>;
}

export async function cancelResumableAgentStream(
  url: string,
  headers: Record<string, string>,
): Promise<void> {
  const response = await fetch(url, { method: 'POST', headers });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
}
