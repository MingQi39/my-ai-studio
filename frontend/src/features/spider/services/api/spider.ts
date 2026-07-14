import { SPIDER_API_BASE, spiderHeaders } from '@/features/spider/services/api/client';
import { getToken } from '@/services/api';

export interface SpiderWorkspaceFile {
  name: string;
  size: number;
  modified_at?: string | null;
}

export interface SpiderWorkspaceResponse {
  session_id: string;
  workspace_path: string;
  volume_name?: string;
  files: SpiderWorkspaceFile[];
}

function isHtmlFilename(fileName: string): boolean {
  const lower = fileName.toLowerCase();
  return lower.endsWith('.html') || lower.endsWith('.htm');
}

export async function fetchSpiderWorkspace(sessionId: string): Promise<SpiderWorkspaceResponse> {
  const response = await fetch(`${SPIDER_API_BASE}/workspace/${sessionId}`, {
    headers: spiderHeaders(),
  });
  if (!response.ok) {
    throw new Error(`Failed to load workspace: ${response.status}`);
  }
  return response.json();
}

function spiderBlobHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

export async function fetchSpiderWorkspaceFileBlob(
  sessionId: string,
  fileName: string,
  options?: { forPreview?: boolean },
): Promise<Blob> {
  const forPreview = options?.forPreview === true && isHtmlFilename(fileName);
  const path = forPreview
    ? `${SPIDER_API_BASE}/workspace/${sessionId}/files/${encodeURIComponent(fileName)}/html-preview`
    : `${SPIDER_API_BASE}/workspace/${sessionId}/files/${encodeURIComponent(fileName)}`;
  const response = await fetch(path, { headers: spiderBlobHeaders() });
  if (!response.ok) {
    throw new Error(`Failed to load file: ${response.status}`);
  }
  return response.blob();
}

export async function fetchSpiderWorkspaceFileText(sessionId: string, fileName: string): Promise<string> {
  const blob = await fetchSpiderWorkspaceFileBlob(sessionId, fileName);
  return blob.text();
}

export async function downloadSpiderWorkspaceFile(sessionId: string, fileName: string): Promise<void> {
  const blob = await fetchSpiderWorkspaceFileBlob(sessionId, fileName);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}
