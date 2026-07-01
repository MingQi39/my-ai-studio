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
};

export type StudioChatStreamBuffers = {
  thinking: string;
  content: string;
};
