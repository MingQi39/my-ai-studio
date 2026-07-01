import type { Message } from '@/features/travel/stores/useChatStore';

export interface CompareTurn {
  user: Message;
  llm?: Message;
  agent?: Message;
}

/** 将消息列表按「用户提问 + LLM/Agent 双回答」分组 */
export function groupCompareTurns(messages: Message[]): CompareTurn[] {
  const turns: CompareTurn[] = [];

  for (const msg of messages) {
    if (msg.role === 'user') {
      turns.push({ user: msg });
      continue;
    }

    const current = turns[turns.length - 1];
    if (!current) continue;

    if (msg.mode === 'llm') {
      current.llm = msg;
    } else if (msg.mode === 'agent') {
      current.agent = msg;
    }
  }

  return turns;
}
