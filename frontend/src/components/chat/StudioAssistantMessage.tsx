import { useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { MessageContent } from '@/components/MessageContent';
import { AssistantMessageShell } from './AssistantMessageShell';
import { ChatToolRunBlock, type ChatToolRun } from './ChatToolRunBlock';
import { GeneratingIndicator } from './GeneratingIndicator';
import { ThinkingBlock } from './ThinkingBlock';
import { ToolExecutionBlock } from './ToolExecutionBlock';
import { StreamRecoveryPrompt } from './StreamRecoveryPrompt';
import { SpiderTodoCard } from '@/features/spider/components/SpiderTodoCard';
import type { SpiderTodoItem } from '@/features/spider/types/todo';

export type StudioAssistantMessageProps = {
  thinking?: string;
  statusLabel?: string;
  isThinking?: boolean;
  todos?: SpiderTodoItem[];
  toolRuns?: ChatToolRun[];
  tool?: {
    name: string;
    code: string;
    output?: string;
    status: 'running' | 'completed';
  };
  content?: string;
  /** Optional structured failure UI (e.g. SpiderFailureCard). */
  failureSlot?: ReactNode;
  isDarkMode?: boolean;
  recoveryPrompt?: 'interrupted';
  onRecoveryRetry?: () => void;
  isRecoveryRetrying?: boolean;
};

function isWriteTodosRun(run: ChatToolRun): boolean {
  return run.raw_tool_name === 'write_todos' || run.tool_name === 'write_todos';
}

export function StudioAssistantMessage({
  thinking,
  statusLabel,
  isThinking,
  todos,
  toolRuns,
  tool,
  content,
  failureSlot,
  isDarkMode = false,
  recoveryPrompt,
  onRecoveryRetry,
  isRecoveryRetrying = false,
}: StudioAssistantMessageProps) {
  const { t } = useTranslation();
  const [showToolDetails, setShowToolDetails] = useState(false);

  const hasTodoCard = Boolean(todos && todos.length > 0);
  const visibleToolRuns = toolRuns?.filter(
    (run) => !isWriteTodosRun(run) && run.tool_name !== 'execute_python',
  );
  const hiddenToolRuns = toolRuns?.filter((run) => isWriteTodosRun(run)) ?? [];

  return (
    <AssistantMessageShell layout="studio">
      {hasTodoCard && todos && <SpiderTodoCard todos={todos} isDarkMode={isDarkMode} />}

      {thinking && <ThinkingBlock text={thinking} isStreaming={isThinking} isDarkMode={isDarkMode} />}

      {statusLabel && isThinking && (
        <GeneratingIndicator layout="spinner" label={statusLabel} />
      )}

      {visibleToolRuns?.map((run, index) => (
        <ChatToolRunBlock key={`${run.tool_name}-${index}`} run={run} isDarkMode={isDarkMode} />
      ))}

      {hiddenToolRuns.length > 0 && (
        <div className="text-xs">
          <button
            type="button"
            className="text-[var(--text-secondary)] underline-offset-2 hover:underline"
            onClick={() => setShowToolDetails((v) => !v)}
          >
            {t('spider.chat.todos.toolDetails')}
          </button>
          {showToolDetails && (
            <div className="mt-2 flex flex-col gap-2">
              {hiddenToolRuns.map((run, index) => (
                <ChatToolRunBlock
                  key={`hidden-${run.tool_name}-${index}`}
                  run={run}
                  isDarkMode={isDarkMode}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {tool && (
        <ToolExecutionBlock
          code={tool.code}
          output={tool.output}
          status={tool.status}
          isDarkMode={isDarkMode}
        />
      )}

      {failureSlot}

      {content && !failureSlot && (
        <MessageContent content={content} isStreaming={isThinking} isDarkMode={isDarkMode} />
      )}

      {!content && !failureSlot && isThinking && !thinking && !statusLabel && (
        <GeneratingIndicator layout="spinner" label={t('workspace.thinking')} />
      )}

      {recoveryPrompt === 'interrupted' && onRecoveryRetry && (
        <StreamRecoveryPrompt
          onRetry={onRecoveryRetry}
          isRetrying={isRecoveryRetrying}
          isDarkMode={isDarkMode}
        />
      )}
    </AssistantMessageShell>
  );
}
