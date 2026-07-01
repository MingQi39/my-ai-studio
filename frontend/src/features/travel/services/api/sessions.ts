/**
 * Travel session API — reuses main studio sessions with session_type=travel.
 */

import {
  createSession,
  deleteSession,
  getSessionMessages,
  listSessions,
  type MessageResponse,
  type SessionResponse,
} from '@/services/api';
import type { Message, ReActStep } from '@/features/travel/stores/useChatStore';

const TRAVEL_META_KEY = 'travel_meta';

function parseTravelMeta(toolCalls: Array<Record<string, unknown>> | null | undefined) {
  if (!toolCalls) return null;
  for (const item of toolCalls) {
    if (item.type === TRAVEL_META_KEY) return item;
  }
  return null;
}

function mapStoredMode(mode: string | undefined): Message['mode'] | undefined {
  if (mode === 'llm' || mode === 'compare_llm') return 'llm';
  if (mode === 'agent' || mode === 'compare_agent') return 'agent';
  return undefined;
}

export function mapStoredMessageToChat(msg: MessageResponse): Message {
  const meta = parseTravelMeta(msg.tool_calls);
  const mode = mapStoredMode(meta?.mode as string | undefined);
  const thinkingSteps = (meta?.thinking_steps as ReActStep[] | undefined) ?? undefined;

  return {
    id: msg.id,
    role: msg.role === 'assistant' ? 'assistant' : 'user',
    content: msg.content,
    mode,
    thinkingSteps,
    timestamp: new Date(msg.created_at).getTime(),
  };
}

export async function listTravelSessions(): Promise<SessionResponse[]> {
  const response = await listSessions(1, 50, false, 'travel');
  return response.items;
}

export async function createTravelSession(title?: string): Promise<SessionResponse> {
  return createSession({
    title: title || '旅行规划',
    session_type: 'travel',
  });
}

export async function loadTravelSessionMessages(sessionId: string): Promise<Message[]> {
  const messages = await getSessionMessages(sessionId, 100);
  return messages.map(mapStoredMessageToChat).reverse();
}

export async function removeTravelSession(sessionId: string): Promise<void> {
  await deleteSession(sessionId);
}
