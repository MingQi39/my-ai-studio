import type { ChatToolRun } from '@/components/chat';

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
  isThinking?: boolean;
  tool?: {
    name: string;
    code: string;
    output?: string;
    status: 'running' | 'completed';
  };
  toolRuns?: ChatToolRun[];
  /** 后端标记：该条 assistant 是否已生成完成 */
  isComplete?: boolean;
  /** 流式恢复失败时，在对话内展示重试提示 */
  recoveryPrompt?: 'interrupted';
};

export type StudioChatStreamBuffers = {
  thinking: string;
  content: string;
};
