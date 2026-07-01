import type { Message } from '@/features/travel/stores/useChatStore';
import type { ToolEvidenceItem } from '@/features/travel/types/itinerary';

const LOADING_CONTENT_PATTERN = /^[🔄💭🔍✍️❌]|^(正在|等待)/;

export function isValidAssistantPlanContent(content: string): boolean {
  const text = content.trim();
  if (!text || text.startsWith('❌')) return false;
  if (LOADING_CONTENT_PATTERN.test(text)) return false;
  return text.length >= 30;
}

export function computePlanFingerprint(userRequest: string, assistantPlan: string): string {
  return `${userRequest.trim()}::${assistantPlan.trim().slice(0, 120)}`;
}

export function getPlanFingerprint(messages: Message[]): string {
  const pair = extractLatestPlanPair(messages);
  if (!pair) return '';
  return computePlanFingerprint(pair.userRequest, pair.assistantPlan);
}

export function hasExportablePlanContent(messages: Message[]): boolean {
  return extractLatestPlanPair(messages) !== null;
}

export function extractLatestPlanPair(messages: Message[]): {
  userRequest: string;
  assistantPlan: string;
  dataVerified: boolean;
} | null {
  const assistantMessages = messages.filter(
    (msg) => msg.role === 'assistant' && isValidAssistantPlanContent(msg.content),
  );
  if (assistantMessages.length === 0) return null;

  const latestAssistant = assistantMessages[assistantMessages.length - 1];
  const latestAssistantIndex = messages.lastIndexOf(latestAssistant);
  const userMessagesBefore = messages
    .slice(0, latestAssistantIndex)
    .filter((msg) => msg.role === 'user');
  const relatedUser = userMessagesBefore[userMessagesBefore.length - 1];
  if (!relatedUser?.content.trim()) return null;

  return {
    userRequest: relatedUser.content.trim(),
    assistantPlan: latestAssistant.content.trim(),
    dataVerified: latestAssistant.mode === 'agent',
  };
}

export function extractToolEvidence(messages: Message[]): ToolEvidenceItem[] {
  const latestAgent = [...messages]
    .reverse()
    .find((msg) => msg.role === 'assistant' && msg.mode === 'agent' && msg.thinkingSteps?.length);

  if (!latestAgent?.thinkingSteps) return [];

  const evidence: ToolEvidenceItem[] = [];
  for (const step of latestAgent.thinkingSteps) {
    for (const toolCall of step.toolCalls ?? []) {
      if (toolCall.status === 'success' && toolCall.result) {
        evidence.push({
          tool_name: toolCall.tool_name,
          result: toolCall.result,
        });
      }
    }
  }
  return evidence;
}
