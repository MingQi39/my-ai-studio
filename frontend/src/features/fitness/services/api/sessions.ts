import type { ChatToolRun } from '@/components/chat';
import {
  createSession,
  deleteSession,
  getSessionMessages,
  listSessions,
  type MessageResponse,
  type SessionResponse,
} from '@/services/api';

import type { StudioChatMessage } from '@/hooks/studioChat/types';
import { FITNESS_TOOL_LABELS } from '@/features/fitness/utils/fitnessUi';

const FITNESS_META_KEY = 'fitness_meta';

function parseFitnessMeta(toolCalls: Array<Record<string, unknown>> | null | undefined) {
  if (!toolCalls) return null;
  for (const item of toolCalls) {
    if (item.type === FITNESS_META_KEY) return item;
  }
  return null;
}

function mapToolTraceStatus(status: unknown): ChatToolRun['status'] {
  if (status === 'error') return 'error';
  if (status === 'pending' || status === 'running') return 'running';
  return 'completed';
}

function formatToolOutput(result: unknown, error?: unknown): string | undefined {
  if (error != null) {
    return typeof error === 'string' ? error : JSON.stringify(error, null, 2);
  }
  if (result == null) return undefined;
  return typeof result === 'string' ? result : JSON.stringify(result, null, 2);
}

function mapToolTraceToRuns(toolTrace: unknown): ChatToolRun[] | undefined {
  if (!Array.isArray(toolTrace) || toolTrace.length === 0) return undefined;

  return toolTrace.map((entry, index) => {
    const raw = entry as Record<string, unknown>;
    const toolName = String(raw.tool_name ?? 'unknown');
    return {
      call_id: String(raw.id ?? raw.call_id ?? `restored-${index}`),
      tool_name: FITNESS_TOOL_LABELS[toolName] ?? toolName,
      tool_input: (raw.tool_args ?? raw.args) as Record<string, unknown> | undefined,
      tool_output: formatToolOutput(raw.result, raw.error),
      status: mapToolTraceStatus(raw.status),
    };
  });
}

export function mapStoredMessageToChat(msg: MessageResponse): StudioChatMessage {
  const role = msg.role === 'assistant' ? 'assistant' : msg.role === 'user' ? 'user' : 'user';
  const meta = parseFitnessMeta(msg.tool_calls);
  const toolRuns = mapToolTraceToRuns(meta?.tool_trace);

  return {
    id: msg.id,
    role: role as 'user' | 'assistant',
    content: msg.content,
    ...(toolRuns ? { toolRuns } : {}),
  };
}

export async function listFitnessSessions(): Promise<SessionResponse[]> {
  const response = await listSessions(1, 50, false, 'fitness');
  return response.items;
}

export async function createFitnessSession(title?: string): Promise<SessionResponse> {
  return createSession({
    title: title || 'Fitness',
    session_type: 'fitness',
  });
}

export async function loadFitnessSessionMessages(sessionId: string): Promise<StudioChatMessage[]> {
  const messages = await getSessionMessages(sessionId, 100);
  return messages.map(mapStoredMessageToChat).reverse();
}

export function extractLatestRecommendations(messages: MessageResponse[]): unknown[] {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const meta = parseFitnessMeta(messages[i].tool_calls);
    const recs = meta?.recommendations;
    if (Array.isArray(recs) && recs.length > 0) return recs;
  }
  return [];
}

export async function loadFitnessSession(sessionId: string): Promise<{
  messages: StudioChatMessage[];
  recommendations: unknown[];
}> {
  const rawMessages = await getSessionMessages(sessionId, 100);
  return {
    messages: rawMessages.map(mapStoredMessageToChat).reverse(),
    recommendations: extractLatestRecommendations(rawMessages),
  };
}

export async function removeFitnessSession(sessionId: string): Promise<void> {
  await deleteSession(sessionId);
}

