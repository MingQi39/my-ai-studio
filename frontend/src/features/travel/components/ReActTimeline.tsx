import { MessageContent } from '@/components/MessageContent';
import type { ReActStep, ToolCall } from '@/features/travel/types/react';
import {
  getReactStepColor,
  getReactStepIcon,
  getReactStepLabel,
} from '@/features/travel/utils/reactStepDisplay';

type ReActTimelineStepProps = {
  icon: React.ReactNode;
  color: string;
  label: string;
  content: React.ReactNode;
  isLast: boolean;
};

export function ReActTimelineStep({
  icon,
  color,
  label,
  content,
  isLast,
}: ReActTimelineStepProps) {
  const colorMap: Record<string, string> = {
    blue: 'bg-blue-500',
    purple: 'bg-purple-500',
    orange: 'bg-orange-500',
    green: 'bg-emerald-500',
  };

  return (
    <div className={`relative pl-8 ${isLast ? '' : 'pb-8'}`}>
      <div
        className={`absolute left-0 top-1.5 w-6 h-6 rounded-full ${colorMap[color] || 'bg-blue-500'} flex items-center justify-center text-white shadow-sm ring-4 ring-white dark:ring-[#151E2E] z-10`}
      >
        {icon}
      </div>
      <div className="mb-2">
        <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">{label}</span>
      </div>
      <div>{content}</div>
    </div>
  );
}

type ReActStepDetailProps = {
  content: string;
  toolCalls?: ToolCall[];
  isDarkMode?: boolean;
};

export function ReActStepDetail({ content, toolCalls, isDarkMode = false }: ReActStepDetailProps) {
  return (
    <div className="w-full min-w-0">
      <div className="min-w-0 max-w-full overflow-hidden bg-white dark:bg-[#151E2E] rounded-lg p-3 border border-slate-200 dark:border-slate-800 text-sm text-slate-700 dark:text-slate-300 mb-2 shadow-sm">
        <MessageContent content={content} isDarkMode={isDarkMode} />
      </div>

      {toolCalls && toolCalls.length > 0 && (
        <div className="mt-3 space-y-2">
          <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-2">🔧 工具调用详情：</div>
          {toolCalls.map((toolCall) => (
            <div
              key={toolCall.id}
              className="bg-white dark:bg-[#0F172A] rounded-lg p-3 border border-slate-200 dark:border-slate-700 text-xs"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono font-semibold text-[#3B82F6]">{toolCall.tool_name}</span>
                <span
                  className={`px-2 py-0.5 rounded text-xs font-medium ${
                    toolCall.status === 'success'
                      ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                      : toolCall.status === 'error'
                        ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
                        : 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400'
                  }`}
                >
                  {toolCall.status === 'success'
                    ? '✅ 成功'
                    : toolCall.status === 'error'
                      ? '❌ 失败'
                      : '⏳ 执行中'}
                </span>
              </div>

              <div className="space-y-1 text-slate-600 dark:text-slate-400">
                <div>
                  <span className="font-semibold">参数：</span>
                  <code className="ml-1 text-xs bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded">
                    {JSON.stringify(toolCall.tool_args)}
                  </code>
                </div>

                {toolCall.result && (
                  <div>
                    <span className="font-semibold">结果：</span>
                    <div className="mt-1 text-xs whitespace-pre-wrap break-words [overflow-wrap:anywhere] bg-slate-50 dark:bg-slate-900 p-2 rounded border border-slate-200 dark:border-slate-700 max-h-32 overflow-y-auto">
                      {toolCall.result}
                    </div>
                  </div>
                )}

                {toolCall.duration_ms && (
                  <div className="text-xs text-slate-500">⏱️ 耗时：{toolCall.duration_ms}ms</div>
                )}

                {toolCall.error && (
                  <div className="text-xs text-red-600 dark:text-red-400">⚠️ 错误：{toolCall.error}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

type ReActTimelineProps = {
  steps: ReActStep[];
  isDarkMode?: boolean;
  className?: string;
};

export function ReActTimeline({ steps, isDarkMode = false, className }: ReActTimelineProps) {
  return (
    <div className={className}>
      <div className="pl-2 relative">
        <div className="absolute left-[19px] top-2 bottom-0 w-[2px] bg-slate-100 dark:bg-slate-800 z-0" />

        {steps.map((step, index) => (
          <ReActTimelineStep
            key={step.sequence}
            icon={getReactStepIcon(step.type)}
            color={getReactStepColor(step.type)}
            label={`${index + 1}. ${getReactStepLabel(step.type)}`}
            isLast={index === steps.length - 1}
            content={
              <ReActStepDetail content={step.content} toolCalls={step.toolCalls} isDarkMode={isDarkMode} />
            }
          />
        ))}
      </div>
    </div>
  );
}
