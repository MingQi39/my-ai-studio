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
import { normalizeSpiderTodos } from '@/features/spider/types/todo';

const SPIDER_META_KEY = 'spider_meta';

export interface SpiderSessionRestore {
  messages: StudioChatMessage[];
  targetUrl: string | null;
}

function parseSpiderMeta(toolCalls: Array<Record<string, unknown>> | null | undefined) {
  if (!toolCalls) return null;
  for (const item of toolCalls) {
    if (item.type === SPIDER_META_KEY) return item;
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
      tool_name: toolName,
      raw_tool_name:
        typeof raw.raw_tool_name === 'string'
          ? raw.raw_tool_name
          : toolName === 'write_todos'
            ? 'write_todos'
            : undefined,
      tool_input: (raw.tool_args ?? raw.args) as Record<string, unknown> | undefined,
      tool_output: formatToolOutput(raw.result, raw.error),
      status: mapToolTraceStatus(raw.status),
    };
  });
}

export function mapStoredMessageToChat(msg: MessageResponse): StudioChatMessage {
  const role = msg.role === 'assistant' ? 'assistant' : msg.role === 'user' ? 'user' : 'user';
  const meta = parseSpiderMeta(msg.tool_calls);
  const toolRuns = mapToolTraceToRuns(meta?.tool_trace);
  const todos = normalizeSpiderTodos(meta?.todos);
  const failureRaw = meta?.failure as Record<string, unknown> | undefined;
  const failure =
    failureRaw && typeof failureRaw === 'object'
      ? {
          code: typeof failureRaw.code === 'string' ? failureRaw.code : undefined,
          title:
            typeof failureRaw.title === 'string' && failureRaw.title.trim()
              ? failureRaw.title
              : '任务执行失败',
          detail: typeof failureRaw.detail === 'string' ? failureRaw.detail : undefined,
          hints: Array.isArray(failureRaw.hints)
            ? failureRaw.hints.filter((item): item is string => typeof item === 'string')
            : undefined,
          stage: typeof failureRaw.stage === 'string' ? failureRaw.stage : undefined,
          recoverable: Boolean(failureRaw.recoverable),
        }
      : undefined;

  return {
    id: msg.id,
    role: role as 'user' | 'assistant',
    content: failure ? '' : msg.content,
    isComplete: msg.is_complete !== false,
    ...(toolRuns ? { toolRuns } : {}),
    ...(todos.length > 0 ? { todos } : {}),
    ...(failure ? { failure } : {}),
  };
}

export async function listSpiderSessions(): Promise<SessionResponse[]> {
  const response = await listSessions(1, 50, false, 'spider');
  return response.items;
}

export async function createSpiderSession(title?: string): Promise<SessionResponse> {
  return createSession({
    title: title || 'Spider',
    session_type: 'spider',
  });
}

export function extractTargetUrlFromMessages(messages: MessageResponse[]): string | null {
  // API returns messages newest-first; use the latest user message that recorded a target URL.
  for (const msg of messages) {
    const meta = parseSpiderMeta(msg.tool_calls);
    if (typeof meta?.target_url === 'string' && meta.target_url.trim()) {
      return meta.target_url.trim();
    }
  }
  return null;
}

export async function loadSpiderSession(sessionId: string): Promise<SpiderSessionRestore> {
  const messages = await getSessionMessages(sessionId, 100);
  const targetUrl = extractTargetUrlFromMessages(messages);

  return {
    messages: messages.map(mapStoredMessageToChat).reverse(),
    targetUrl,
  };
}

export async function removeSpiderSession(sessionId: string): Promise<void> {
  await deleteSession(sessionId);
}
