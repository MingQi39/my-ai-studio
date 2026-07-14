import type { ChatToolRun } from '@/components/chat';
import type { SpiderTodoItem } from '@/features/spider/types/todo';

export type SpiderFailureInfo = {
  code?: string;
  title: string;
  detail?: string;
  hints?: string[];
  stage?: string;
  recoverable?: boolean;
};

export type StudioChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  images?: Array<{
    id: string;
    url: string;
    name: string;
  }>;
  thinking?: string;
  /** Ephemeral in-flight status (e.g. sub-agent working); not persisted. */
  statusLabel?: string;
  isThinking?: boolean;
  tool?: {
    name: string;
    code: string;
    output?: string;
    status: 'running' | 'completed';
  };
  toolRuns?: ChatToolRun[];
  /** DeepAgent write_todos snapshot; omit when task has no plan. */
  todos?: SpiderTodoItem[];
  /** Spider structured failure card (persisted via spider_meta). */
  failure?: SpiderFailureInfo;
  /** 后端标记：该条 assistant 是否已生成完成 */
  isComplete?: boolean;
  /** 流式恢复失败时，在对话内展示重试提示 */
  recoveryPrompt?: 'interrupted';
};

export type StudioChatStreamBuffers = {
  thinking: string;
  content: string;
};
