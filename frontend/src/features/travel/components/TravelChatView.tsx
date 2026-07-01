import React, { useState } from 'react';
import {
  GitCompare,
  Brain,
  CheckCircle2,
  AlertTriangle,
  Activity,
  FileDown,
  Copy,
  Check,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  AssistantMessageShell,
  ChatEmptyState,
  ChatInputArea,
  ChatJumpToBottom,
  GeneratingIndicator,
  UserMessageBubble,
} from '@/components/chat';
import { MessageContent } from '@/components/MessageContent';
import { ActiveModelBadge } from '@/components/ActiveModelBadge';
import { TravelReActTrace } from '@/features/travel/components/TravelReActTrace';
import { PlanExportToolbar } from '@/features/travel/components/PlanExportToolbar';
import { useChatStore, type Message } from '@/features/travel/stores/useChatStore';
import { useCompare } from '@/features/travel/hooks/useCompare';
import { useChat } from '@/features/travel/hooks/useChat';
import { useChatAutoScroll } from '@/features/travel/hooks/useChatAutoScroll';
import { useTravelSessionRestore } from '@/features/travel/hooks/useTravelSessionRestore';
import { useTravelSessionRoute } from '@/features/travel/hooks/useTravelSessionRoute';
import { groupCompareTurns, type CompareTurn } from '@/features/travel/utils/compareTurns';
import { branding } from '@/features/travel/config/branding';
import { copyTextToClipboard } from '@/features/travel/utils/exportPlan';

export interface TravelChatViewProps {
  isDarkMode: boolean;
  onOpenModelSettings?: () => void;
  selectedModel?: string;
}

export function TravelChatView({
  isDarkMode,
  onOpenModelSettings,
  selectedModel = '',
}: TravelChatViewProps) {
  const { t } = useTranslation();
  const { messages, isGenerating, isLoadingHistory, chatMode, setChatMode } = useChatStore();
  useTravelSessionRoute();
  useTravelSessionRestore();
  const { sendMessage: sendChatMessage } = useChat();
  const { sendMessage: sendCompareMessage } = useCompare();
  const [inputValue, setInputValue] = useState('');
  const [isCompareMode, setIsCompareMode] = useState(false);
  const [exportToolbarOpen, setExportToolbarOpen] = useState(false);
  const { scrollContainerRef, scrollSentinelRef, showJumpButton, scrollToBottom } = useChatAutoScroll({
    deps: [messages, isGenerating],
    active: messages.length > 0,
  });

  const handleSend = (textStr: string | React.FormEvent) => {
    const text = typeof textStr === 'string' ? textStr : inputValue;
    if (!text.trim() || isGenerating) return;

    setInputValue('');
    scrollToBottom('auto');
    if (isCompareMode) {
      sendCompareMessage(text).catch((err) => {
        console.error(err);
        toast.error(err instanceof Error ? err.message : '发送失败');
      });
    } else {
      sendChatMessage(text).catch((err) => {
        console.error(err);
        toast.error(err instanceof Error ? err.message : '发送失败');
      });
    }
  };

  return (
    <div className="flex-1 flex flex-col w-full h-full relative">
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto w-full flex flex-col items-center"
      >
        {messages.length === 0 ? (
          <ChatEmptyState
            loading={isLoadingHistory}
            loadingMessage="正在加载对话历史…"
            logoAlt={branding.logoAlt}
            title={branding.tagline}
            subtitle="有什么旅行规划可以帮忙的？"
            quickPrompts={['3天杭州游', '北京亲子游', '成都美食之旅'].map((tag) => ({
              id: tag,
              title: tag,
              description: '点击自动输入并发送，快速体验当前模式的对话效果',
              onSelect: () => handleSend(`请帮我规划一个${tag}，预算适中即可。`),
            }))}
          />
        ) : isCompareMode ? (
          <div className="w-full max-w-7xl px-4 py-8 flex flex-col pb-10">
            {groupCompareTurns(messages).map((turn, idx, arr) => (
              <CompareTurnBlock
                key={turn.user.id}
                turn={turn}
                showLoading={isGenerating && idx === arr.length - 1}
                isDarkMode={isDarkMode}
              />
            ))}
            <div ref={scrollSentinelRef} className="h-px w-full shrink-0" aria-hidden />
          </div>
        ) : (
          <div className="w-full max-w-4xl px-4 py-4 flex flex-col pb-10">
            <PlanExportToolbar
              messages={messages}
              disabled={isGenerating}
              visible={exportToolbarOpen}
              onClose={() => setExportToolbarOpen(false)}
            />
            {messages.map((msg) => (
              <TravelChatMessage key={msg.id} msg={msg} isDarkMode={isDarkMode} />
            ))}

            {isGenerating && <GeneratingIndicator layout="avatar" icon={<Brain size={16} />} />}
            <div ref={scrollSentinelRef} className="h-px w-full shrink-0" aria-hidden />
          </div>
        )}
      </div>

      {showJumpButton && messages.length > 0 && (
        <ChatJumpToBottom onClick={() => scrollToBottom('smooth')} />
      )}

      <div
        className={`w-full mx-auto px-4 pb-2 pt-2 shrink-0 bg-gradient-to-t from-white via-white to-transparent dark:from-[#0F172A] dark:via-[#0F172A] ${isCompareMode ? 'max-w-7xl' : 'max-w-4xl'}`}
      >
        <ChatInputArea
          layout="travel"
          value={inputValue}
          onChange={setInputValue}
          onSubmit={() => handleSend(inputValue)}
          disabled={isGenerating}
          placeholder="发送消息..."
          innerClassName="flex flex-col relative w-full shadow-sm bg-white dark:bg-[#1E293B] border border-slate-300 dark:border-slate-700 rounded-2xl focus-within:ring-2 focus-within:ring-[#3B82F6]/50 focus-within:border-[#3B82F6] transition-all overflow-hidden"
          header={
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-100 dark:border-slate-800/60 bg-slate-50/80 dark:bg-slate-900/80 backdrop-blur-sm">
              <span className="text-[11px] font-bold text-slate-500 dark:text-slate-400 mr-1 uppercase tracking-wider">
                对话模式
              </span>
              <div className="flex bg-slate-200/50 dark:bg-slate-800/50 p-0.5 rounded-lg">
                <button
                  onClick={() => {
                    setIsCompareMode(false);
                    setChatMode('agent');
                  }}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
                    !isCompareMode && chatMode === 'agent'
                      ? 'bg-white dark:bg-[#1E293B] text-[#3B82F6] shadow-sm'
                      : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                  }`}
                >
                  <Brain size={14} /> Agent (ReAct)
                </button>
                <button
                  onClick={() => {
                    setIsCompareMode(false);
                    setChatMode('llm');
                  }}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
                    !isCompareMode && chatMode === 'llm'
                      ? 'bg-white dark:bg-[#1E293B] text-blue-500 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                  }`}
                >
                  <Activity size={14} /> 原生 LLM
                </button>
                <button
                  onClick={() => setIsCompareMode(true)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
                    isCompareMode
                      ? 'bg-white dark:bg-[#1E293B] text-emerald-500 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                  }`}
                >
                  <GitCompare size={14} /> 对比模式
                </button>
              </div>
              {messages.length > 0 && !isCompareMode && (
                <button
                  type="button"
                  onClick={() => setExportToolbarOpen(true)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold transition-all ${
                    exportToolbarOpen
                      ? 'bg-white dark:bg-[#1E293B] text-emerald-600 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                  }`}
                  aria-expanded={exportToolbarOpen}
                >
                  <FileDown size={14} />
                  {t('travel.export.toolbarLabel')}
                </button>
              )}
              {onOpenModelSettings && (
                <ActiveModelBadge
                  model={selectedModel}
                  onClick={onOpenModelSettings}
                  variant="compact"
                  className="ml-auto max-w-[180px] sm:max-w-[220px]"
                />
              )}
            </div>
          }
          hint={
            <div className="text-center mt-3 text-[11px] text-slate-400 dark:text-slate-500">
              内容由 AI 生成，Agent 模式将调用外部工具验证数据真实性，LLM 模式可能会产生幻觉。
            </div>
          }
        />
      </div>
    </div>
  );
}

function CompareColumnPanel({
  title,
  icon,
  accent,
  badge,
  showLoading,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  accent: 'blue' | 'emerald';
  badge: string;
  showLoading?: boolean;
  children?: React.ReactNode;
}) {
  const accentBorder = accent === 'blue' ? 'border-t-blue-500' : 'border-t-emerald-500';
  const accentText = accent === 'blue' ? 'text-blue-500' : 'text-emerald-500';
  const dotClassName = accent === 'blue' ? 'bg-blue-500' : 'bg-emerald-500';

  return (
    <div
      className={`flex flex-col rounded-xl border border-slate-200 dark:border-slate-800 border-t-2 ${accentBorder} overflow-hidden bg-white dark:bg-[#151E2E] shadow-sm min-h-[120px]`}
    >
      <div className="px-4 py-2.5 border-b border-slate-100 dark:border-slate-800 bg-slate-50/80 dark:bg-[#1E293B]/60 flex items-center gap-2 shrink-0">
        <span className={accentText}>{icon}</span>
        <span className="text-xs font-bold text-slate-700 dark:text-slate-200">{title}</span>
        <span className={`text-[10px] ml-auto ${accent === 'blue' ? 'text-amber-500' : 'text-emerald-500'}`}>
          {badge}
        </span>
        {showLoading && (
          <GeneratingIndicator layout="dots" dotClassName={dotClassName} dotSize="sm" className="ml-2" />
        )}
      </div>
      <div className="p-4 flex-1">
        {children ?? <p className="text-sm text-slate-400 italic py-2">等待回复…</p>}
      </div>
    </div>
  );
}

function CompareTurnBlock({
  turn,
  showLoading,
  isDarkMode,
}: {
  turn: CompareTurn;
  showLoading: boolean;
  isDarkMode: boolean;
}) {
  return (
    <div className="mb-12">
      <UserMessageBubble content={turn.user.content} variant="travel" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-5">
        <CompareColumnPanel
          title="原生 LLM"
          icon={<Activity size={14} />}
          accent="blue"
          badge="未验证"
          showLoading={showLoading && !!turn.llm}
        >
          {turn.llm && (
            <TravelChatMessage msg={turn.llm} layout="column" hideFooter isDarkMode={isDarkMode} />
          )}
        </CompareColumnPanel>
        <CompareColumnPanel
          title="ReAct Agent"
          icon={<Brain size={14} />}
          accent="emerald"
          badge="工具验证"
          showLoading={showLoading && !!turn.agent}
        >
          {turn.agent && (
            <TravelChatMessage msg={turn.agent} layout="column" hideFooter isDarkMode={isDarkMode} />
          )}
        </CompareColumnPanel>
      </div>
    </div>
  );
}

function TravelChatMessage({
  msg,
  layout = 'default',
  hideFooter = false,
  isDarkMode = false,
}: {
  msg: Message;
  layout?: 'default' | 'column';
  hideFooter?: boolean;
  isDarkMode?: boolean;
}) {
  const { t } = useTranslation();
  const isColumn = layout === 'column';
  const [copied, setCopied] = useState(false);

  const handleCopyContent = async () => {
    if (!msg.content.trim()) return;
    try {
      await copyTextToClipboard(msg.content.trim());
      setCopied(true);
      toast.success(t('travel.export.copiedPlan'));
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error(t('travel.export.copyFailed'));
    }
  };

  if (msg.role === 'user') {
    return (
      <UserMessageBubble
        content={msg.content}
        variant="travel"
        className={isColumn ? 'mb-0' : 'mb-8'}
      />
    );
  }

  const footer = !hideFooter ? (
    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] font-medium text-slate-400">
      {msg.mode === 'agent' ? (
        <span className="flex items-center gap-1 text-emerald-500">
          <CheckCircle2 size={12} /> ReAct Agent 生成，数据已验证
        </span>
      ) : (
        <span className="flex items-center gap-1 text-amber-500">
          <AlertTriangle size={12} /> 原生 LLM 预测，未验证真实性
        </span>
      )}
      {msg.content.trim() && (
        <button
          type="button"
          onClick={handleCopyContent}
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-slate-500 opacity-0 transition-opacity hover:bg-slate-100 hover:text-slate-700 group-hover:opacity-100 dark:hover:bg-slate-800 dark:hover:text-slate-200"
        >
          {copied ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
          {copied ? t('travel.export.copiedPlan') : t('travel.export.copyPlan')}
        </button>
      )}
    </div>
  ) : undefined;

  return (
    <AssistantMessageShell
      layout="travel"
      showAvatar={!isColumn}
      avatar={<Brain size={16} />}
      bodyClassName={isColumn ? 'w-full max-w-none' : 'max-w-[80%]'}
      className={isColumn ? 'mb-0' : 'mb-8'}
      footer={footer}
    >
      {msg.mode === 'agent' && msg.thinkingSteps && msg.thinkingSteps.length > 0 && (
        <TravelReActTrace
          steps={msg.thinkingSteps}
          isDarkMode={isDarkMode}
          defaultExpanded={msg.mode === 'agent'}
        />
      )}

      <div className="text-[15px] leading-relaxed py-1 max-w-none">
        <MessageContent content={msg.content} isDarkMode={isDarkMode} />
      </div>
    </AssistantMessageShell>
  );
}
