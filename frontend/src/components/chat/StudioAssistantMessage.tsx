import { useTranslation } from 'react-i18next';
import { MessageContent } from '@/components/MessageContent';
import { AssistantMessageShell } from './AssistantMessageShell';
import { ChatToolRunBlock, type ChatToolRun } from './ChatToolRunBlock';
import { GeneratingIndicator } from './GeneratingIndicator';
import { ThinkingBlock } from './ThinkingBlock';
import { ToolExecutionBlock } from './ToolExecutionBlock';

export type StudioAssistantMessageProps = {
  thinking?: string;
  isThinking?: boolean;
  toolRuns?: ChatToolRun[];
  tool?: {
    name: string;
    code: string;
    output?: string;
    status: 'running' | 'completed';
  };
  content?: string;
  isDarkMode?: boolean;
};

export function StudioAssistantMessage({
  thinking,
  isThinking,
  toolRuns,
  tool,
  content,
  isDarkMode = false,
}: StudioAssistantMessageProps) {
  const { t } = useTranslation();

  return (
    <AssistantMessageShell layout="studio">
      {thinking && <ThinkingBlock text={thinking} isStreaming={isThinking} isDarkMode={isDarkMode} />}

      {toolRuns
        ?.filter((run) => run.tool_name !== 'execute_python')
        .map((run, index) => (
          <ChatToolRunBlock key={`${run.tool_name}-${index}`} run={run} isDarkMode={isDarkMode} />
        ))}

      {tool && (
        <ToolExecutionBlock
          code={tool.code}
          output={tool.output}
          status={tool.status}
          isDarkMode={isDarkMode}
        />
      )}

      {content && (
        <MessageContent content={content} isStreaming={isThinking} isDarkMode={isDarkMode} />
      )}

      {!content && isThinking && !thinking && (
        <GeneratingIndicator layout="spinner" label={t('workspace.thinking')} />
      )}
    </AssistantMessageShell>
  );
}
