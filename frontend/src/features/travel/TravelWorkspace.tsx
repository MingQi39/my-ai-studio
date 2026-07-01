import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
    GitCompare, Brain, Wrench, Settings,
    Send, ChevronDown, ChevronRight, Terminal,
    CheckCircle2, AlertTriangle, Search, Lightbulb, Activity, Code2,
    FileJson, MessageSquare, Play, ListFilter,
    CloudSun, Landmark, Building2, Train, Calculator, UtensilsCrossed, Copy, Check, X, Plus,
    Eye, EyeOff, Save, Plug, AlertCircle, RefreshCw, Loader2, Menu, PanelRight,
    ArrowDown,
    FileDown,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';

// 导入新的状态管理和 Hooks
import { toast } from 'sonner';
import { useChatStore, type Message, type ReActStep, type ToolCall } from '@/features/travel/stores/useChatStore';
import { useCompare } from '@/features/travel/hooks/useCompare';
import { useChat } from '@/features/travel/hooks/useChat';
import { useChatAutoScroll } from '@/features/travel/hooks/useChatAutoScroll';
import { useTravelSessionRestore } from '@/features/travel/hooks/useTravelSessionRestore';
import { useTravelSessionRoute } from '@/features/travel/hooks/useTravelSessionRoute';
import { groupCompareTurns, type CompareTurn } from '@/features/travel/utils/compareTurns';
import { useReactStore } from '@/features/travel/stores/useReactStore';
import { useReactTrace } from '@/features/travel/hooks/useReactTrace';
import { fetchToolsList, testTool, type Tool } from '@/features/travel/services/api/tools';
import { fetchTravelSettings, updateTravelSettings, type TravelSettings } from '@/features/travel/services/api/settings';
import { BrandLogo } from '@/components/BrandLogo';
import { branding } from '@/features/travel/config/branding';
import { PlanExportToolbar } from '@/features/travel/components/PlanExportToolbar';
import { copyTextToClipboard } from '@/features/travel/utils/exportPlan';

interface TravelWorkspaceProps {
    activeTab: string;
    isDarkMode: boolean;
    isSidebarOpen: boolean;
    toggleSidebar: () => void;
    selectedModel: string;
    isControlPanelOpen: boolean;
    toggleControlPanel: () => void;
    onOpenModelSettings?: () => void;
}

export function TravelWorkspace({
    activeTab,
    isDarkMode,
    isSidebarOpen,
    toggleSidebar,
    selectedModel,
    isControlPanelOpen,
    toggleControlPanel,
    onOpenModelSettings,
}: TravelWorkspaceProps) {
    const { t } = useTranslation();
    const [toastConfig, setToastConfig] = useState<{ message: string; type: string } | null>(null);

    const showToast = (message: string, type = 'success') => setToastConfig({ message, type });
    const hideToast = () => setToastConfig(null);

    useEffect(() => {
        if (isDarkMode) {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
    }, [isDarkMode]);

    const pageTitle =
        activeTab === 'chat' ? t('travel.sidebar.chat')
        : activeTab === 'react' ? t('travel.sidebar.react')
        : activeTab === 'tools' ? t('travel.sidebar.tools')
        : t('travel.sidebar.agentSettings');

    return (
        <div className="flex flex-col h-full w-full bg-[var(--bg-main)] text-[var(--text-primary)]">
            {toastConfig && <Toast message={toastConfig.message} type={toastConfig.type} onClose={hideToast} />}

            <header className="h-14 flex-shrink-0 flex items-center justify-between px-4 border-b border-[var(--border-color)]">
                <div className="flex items-center gap-3 min-w-0">
                    {!isSidebarOpen && (
                        <Button variant="ghost" size="icon" onClick={toggleSidebar} className="h-9 w-9">
                            <Menu size={20} />
                        </Button>
                    )}
                    <div className="min-w-0">
                        <h1 className="text-sm font-semibold truncate">{pageTitle}</h1>
                        <p className="text-xs text-[var(--text-secondary)] truncate">{t('sidebar.travelAgent')}</p>
                    </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                        type="button"
                        onClick={onOpenModelSettings}
                        className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono border border-[var(--border-color)] bg-[var(--bg-hover)] hover:border-blue-500/40 transition-colors max-w-[200px]"
                    >
                        <span className="truncate">{selectedModel || t('travel.panel.noModel')}</span>
                    </button>
                    <Button variant="ghost" size="icon" onClick={toggleControlPanel} className="h-9 w-9">
                        <PanelRight size={18} className={isControlPanelOpen ? 'text-blue-500' : ''} />
                    </Button>
                </div>
            </header>

            <main className="flex-1 min-h-0 overflow-hidden">
                {activeTab === 'chat' ? (
                    <ChatView onOpenModelSettings={onOpenModelSettings} />
                ) : (
                    <div className="h-full overflow-y-auto p-6 custom-scrollbar">
                        <div className="max-w-6xl mx-auto w-full">
                            {activeTab === 'react' && <ReactView showToast={showToast} selectedModel={selectedModel} />}
                            {activeTab === 'tools' && <ToolsView showToast={showToast} />}
                            {activeTab === 'settings' && (
                                <SettingsView showToast={showToast} onOpenModelSettings={onOpenModelSettings} />
                            )}
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}

/* ================= 页面视图组件 ================= */

function ChatView({ onOpenModelSettings }: { onOpenModelSettings?: () => void }) {
    const { t } = useTranslation();
    const { messages, isGenerating, isLoadingHistory, chatMode, setChatMode } = useChatStore();
    useTravelSessionRoute();
    useTravelSessionRestore();
    const { sendMessage: sendChatMessage } = useChat();
    const { sendMessage: sendCompareMessage } = useCompare();
    const [inputValue, setInputValue] = useState('');
    const [isCompareMode, setIsCompareMode] = useState(false);
    const [exportToolbarOpen, setExportToolbarOpen] = useState(false);
    const {
        scrollContainerRef,
        scrollSentinelRef,
        showJumpButton,
        scrollToBottom,
    } = useChatAutoScroll({
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

            {/* 聊天记录列表区 */}
            <div
                ref={scrollContainerRef}
                className="flex-1 overflow-y-auto w-full flex flex-col items-center"
            >
                {messages.length === 0 ? (
                    isLoadingHistory ? (
                    <div className="flex-1 flex flex-col items-center justify-center w-full px-6 pt-20 pb-10">
                        <Loader2 size={32} className="animate-spin text-[#3B82F6] mb-4" />
                        <p className="text-slate-500 dark:text-slate-400">正在加载对话历史…</p>
                    </div>
                    ) : (
                    <div className="flex-1 flex flex-col items-center justify-center w-full max-w-3xl px-6 animate-in fade-in duration-500 pt-20 pb-10">
                        <BrandLogo size="lg" className="mb-4 opacity-90" alt={branding.logoAlt} />
                        <h1 className="text-3xl font-bold mb-2 tracking-tight text-slate-800 dark:text-slate-100">{branding.tagline}</h1>
                        <p className="text-slate-500 dark:text-slate-400 mb-10">有什么旅行规划可以帮忙的？</p>

                        {/* 快捷输入标签 */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 w-full mb-8">
                            {['3天杭州游', '北京亲子游', '成都美食之旅'].map(tag => (
                                <button
                                    key={tag}
                                    onClick={() => handleSend(`请帮我规划一个${tag}，预算适中即可。`)}
                                    className="flex flex-col items-start p-5 bg-white dark:bg-[#151E2E] border border-slate-200 dark:border-slate-800 hover:border-[#3B82F6] dark:hover:border-[#3B82F6] rounded-2xl transition-all shadow-sm group hover:shadow-md"
                                >
                                    <span className="text-[15px] font-bold text-slate-800 dark:text-slate-200 group-hover:text-[#3B82F6] transition-colors mb-2">✨ {tag}</span>
                                    <span className="text-xs text-slate-500 dark:text-slate-400 text-left">点击自动输入并发送，快速体验当前模式的对话效果</span>
                                </button>
                            ))}
                        </div>
                    </div>
                    )
                ) : isCompareMode ? (
                    <div className="w-full max-w-7xl px-4 py-8 flex flex-col pb-10">
                        {groupCompareTurns(messages).map((turn, idx, arr) => (
                            <CompareTurnBlock
                                key={turn.user.id}
                                turn={turn}
                                showLoading={isGenerating && idx === arr.length - 1}
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
                        {messages.map(msg => <ChatMessage key={msg.id} msg={msg} />)}

                        {isGenerating && (
                            <div className="flex w-full justify-start mb-6">
                                <div className="w-8 h-8 rounded-full bg-[#3B82F6] flex items-center justify-center text-white mr-4 flex-shrink-0 mt-0.5 shadow-sm">
                                    <Brain size={16} />
                                </div>
                                <div className="py-2.5 flex items-center gap-2">
                                    <span className="w-2 h-2 bg-[#3B82F6] rounded-full animate-bounce"></span>
                                    <span className="w-2 h-2 bg-[#3B82F6] rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></span>
                                    <span className="w-2 h-2 bg-[#3B82F6] rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></span>
                                </div>
                            </div>
                        )}
                        <div ref={scrollSentinelRef} className="h-px w-full shrink-0" aria-hidden />
                    </div>
                )}
            </div>

            {showJumpButton && messages.length > 0 && (
                <button
                    type="button"
                    onClick={() => scrollToBottom('smooth')}
                    className="absolute bottom-36 right-6 z-20 flex items-center gap-1.5 rounded-full border border-slate-200 bg-white/95 px-4 py-2 text-sm font-medium text-slate-700 shadow-lg backdrop-blur-sm transition-all hover:border-[#3B82F6] hover:text-[#3B82F6] dark:border-slate-700 dark:bg-[#1E293B]/95 dark:text-slate-200 dark:hover:border-[#3B82F6] dark:hover:text-[#3B82F6]"
                    aria-label="回到底部并恢复自动滚动"
                >
                    <ArrowDown size={16} />
                    回到底部
                </button>
            )}

            {/* 底部固定输入区 */}
            <div className={`w-full mx-auto px-4 pb-2 pt-2 shrink-0 bg-gradient-to-t from-white via-white to-transparent dark:from-[#0F172A] dark:via-[#0F172A] ${isCompareMode ? 'max-w-7xl' : 'max-w-4xl'}`}>
                <div className="flex flex-col relative w-full shadow-sm bg-white dark:bg-[#1E293B] border border-slate-300 dark:border-slate-700 rounded-2xl focus-within:ring-2 focus-within:ring-[#3B82F6]/50 focus-within:border-[#3B82F6] transition-all overflow-hidden">

                    {/* 模式选择器 (Mode Toggle) */}
                    <div className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-100 dark:border-slate-800/60 bg-slate-50/80 dark:bg-slate-900/80 backdrop-blur-sm">
                        <span className="text-[11px] font-bold text-slate-500 dark:text-slate-400 mr-1 uppercase tracking-wider">对话模式</span>
                        <div className="flex bg-slate-200/50 dark:bg-slate-800/50 p-0.5 rounded-lg">
                            <button
                                onClick={() => { setIsCompareMode(false); setChatMode('agent'); }}
                                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold transition-all ${!isCompareMode && chatMode === 'agent'
                                        ? 'bg-white dark:bg-[#1E293B] text-[#3B82F6] shadow-sm'
                                        : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                                    }`}
                            >
                                <Brain size={14} /> Agent (ReAct)
                            </button>
                            <button
                                onClick={() => { setIsCompareMode(false); setChatMode('llm'); }}
                                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold transition-all ${!isCompareMode && chatMode === 'llm'
                                        ? 'bg-white dark:bg-[#1E293B] text-blue-500 shadow-sm'
                                        : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                                    }`}
                            >
                                <Activity size={14} /> 原生 LLM
                            </button>
                            <button
                                onClick={() => setIsCompareMode(true)}
                                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold transition-all ${isCompareMode
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
                            <button
                                onClick={onOpenModelSettings}
                                className="ml-auto text-[11px] font-medium text-[#3B82F6] hover:underline"
                            >
                                模型连接设置 →
                            </button>
                        )}
                    </div>

                    <div className="relative flex items-end">
                        <textarea
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault();
                                    handleSend(inputValue);
                                }
                            }}
                            placeholder="发送消息..."
                            className="w-full max-h-48 min-h-[56px] py-4 pl-4 pr-16 bg-transparent border-none outline-none text-[15px] placeholder-slate-400 resize-none overflow-y-auto text-slate-800 dark:text-slate-200"
                            rows={1}
                        />
                        <button
                            onClick={() => handleSend(inputValue)}
                            disabled={!inputValue.trim() || isGenerating}
                            className={`absolute right-3 bottom-3 p-2 rounded-xl transition-all flex items-center justify-center ${inputValue.trim() && !isGenerating
                                    ? 'bg-[#3B82F6] hover:bg-[#2563EB] text-white shadow-md'
                                    : 'bg-slate-100 dark:bg-slate-800 text-slate-400 cursor-not-allowed'
                                }`}
                        >
                            <Send size={18} />
                        </button>
                    </div>
                </div>
                <div className="text-center mt-3 text-[11px] text-slate-400 dark:text-slate-500">
                    内容由 AI 生成，Agent 模式将调用外部工具验证数据真实性，LLM 模式可能会产生幻觉。
                </div>
            </div>

        </div>
    );
}

function UserMessageBubble({ msg }: { msg: Message }) {
    return (
        <div className="flex w-full justify-end mb-4">
            <div className="max-w-[85%] md:max-w-[65%] text-[15px] leading-relaxed bg-slate-100 dark:bg-[#2A2B32] text-slate-900 dark:text-slate-100 px-5 py-3.5 rounded-3xl">
                {msg.content.split('\n').map((line: string, i: number, arr: string[]) => (
                    <React.Fragment key={i}>
                        {line}
                        {i !== arr.length - 1 && <div className="h-3" />}
                    </React.Fragment>
                ))}
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

    return (
        <div className={`flex flex-col rounded-xl border border-slate-200 dark:border-slate-800 border-t-2 ${accentBorder} overflow-hidden bg-white dark:bg-[#151E2E] shadow-sm min-h-[120px]`}>
            <div className="px-4 py-2.5 border-b border-slate-100 dark:border-slate-800 bg-slate-50/80 dark:bg-[#1E293B]/60 flex items-center gap-2 shrink-0">
                <span className={accentText}>{icon}</span>
                <span className="text-xs font-bold text-slate-700 dark:text-slate-200">{title}</span>
                <span className={`text-[10px] ml-auto ${accent === 'blue' ? 'text-amber-500' : 'text-emerald-500'}`}>{badge}</span>
                {showLoading && (
                    <span className="flex items-center gap-1 ml-2">
                        <span className={`w-1.5 h-1.5 rounded-full animate-bounce ${accentText}`} />
                        <span className={`w-1.5 h-1.5 rounded-full animate-bounce ${accentText}`} style={{ animationDelay: '0.15s' }} />
                        <span className={`w-1.5 h-1.5 rounded-full animate-bounce ${accentText}`} style={{ animationDelay: '0.3s' }} />
                    </span>
                )}
            </div>
            <div className="p-4 flex-1">
                {children ?? (
                    <p className="text-sm text-slate-400 italic py-2">等待回复…</p>
                )}
            </div>
        </div>
    );
}

function CompareTurnBlock({ turn, showLoading }: { turn: CompareTurn; showLoading: boolean }) {
    return (
        <div className="mb-12">
            <UserMessageBubble msg={turn.user} />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-5">
                <CompareColumnPanel
                    title="原生 LLM"
                    icon={<Activity size={14} />}
                    accent="blue"
                    badge="未验证"
                    showLoading={showLoading && !!turn.llm}
                >
                    {turn.llm && <ChatMessage msg={turn.llm} layout="column" hideFooter />}
                </CompareColumnPanel>
                <CompareColumnPanel
                    title="ReAct Agent"
                    icon={<Brain size={14} />}
                    accent="emerald"
                    badge="工具验证"
                    showLoading={showLoading && !!turn.agent}
                >
                    {turn.agent && <ChatMessage msg={turn.agent} layout="column" hideFooter />}
                </CompareColumnPanel>
            </div>
        </div>
    );
}

function ChatMessage({
    msg,
    layout = 'default',
    hideFooter = false,
}: {
    msg: Message;
    layout?: 'default' | 'column';
    hideFooter?: boolean;
}) {
    const { t } = useTranslation();
    const isColumn = layout === 'column';
    const [copied, setCopied] = useState(false);
    // Agent 模式默认展开思考过程
    const [showTrace, setShowTrace] = useState(msg.mode === 'agent');

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

    // 辅助函数
    const getIconForStepType = (type: string) => {
        switch (type) {
            case 'Observe': return <Search size={14} />
            case 'Think': return <Lightbulb size={14} />
            case 'Act': return <Code2 size={14} />
            case 'Verify': return <CheckCircle2 size={14} />
            default: return <Activity size={14} />
        }
    }

    const getColorForStepType = (type: string) => {
        switch (type) {
            case 'Observe': return 'blue'
            case 'Think': return 'purple'
            case 'Act': return 'orange'
            case 'Verify': return 'green'
            default: return 'blue'
        }
    }

    const getStepLabel = (type: string) => {
        const labels: Record<string, string> = {
            'Observe': '观察环境 (Observe)',
            'Think': '思考决策 (Think)',
            'Act': '执行动作 (Act)',
            'Verify': '观察结果 (Verify)'
        }
        return labels[type] || type
    }

    return (
        <div className={`flex w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'} ${isColumn ? 'mb-0' : 'mb-8'} group`}>
            {msg.role === 'assistant' && !isColumn && (
                <div className="w-8 h-8 rounded-full bg-[#3B82F6] flex items-center justify-center text-white mr-4 flex-shrink-0 shadow-sm mt-0.5">
                    <Brain size={16} />
                </div>
            )}

            <div className={`${isColumn ? 'w-full max-w-none' : 'max-w-[80%]'} flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>

                {/* Agent 思考过程模块 (折叠面板) */}
                {msg.role === 'assistant' && msg.mode === 'agent' && msg.thinkingSteps && msg.thinkingSteps.length > 0 && (
                    <div className="mb-3 w-full">
                        <button
                            onClick={() => setShowTrace(!showTrace)}
                            className="flex items-center gap-2 px-3 py-1.5 bg-slate-50 hover:bg-slate-100 dark:bg-[#1E293B]/50 dark:hover:bg-[#1E293B] text-slate-600 dark:text-slate-300 rounded-full text-xs font-medium transition-colors border border-slate-200 dark:border-slate-700/50"
                        >
                            {showTrace ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                            <Activity size={14} className="text-[#3B82F6]" />
                            🧠 思考过程 ({msg.thinkingSteps.length} 步)
                        </button>
                        {showTrace && (
                            <div className="mt-3 mb-4 p-4 bg-slate-50 dark:bg-[#0F172A] border border-slate-200 dark:border-slate-800 rounded-xl text-xs w-full max-h-[60vh] overflow-y-auto scroll-smooth">
                                <div className="pl-2 relative">
                                    <div className="absolute left-[19px] top-2 bottom-0 w-[2px] bg-slate-100 dark:bg-slate-800 z-0"></div>

                                    {msg.thinkingSteps.map((step: any, index: number) => (
                                        <TimelineStep
                                            key={step.sequence}
                                            icon={getIconForStepType(step.type)}
                                            color={getColorForStepType(step.type)}
                                            label={`${index + 1}. ${getStepLabel(step.type)}`}
                                            content={
                                                <div className="w-full">
                                                    <div className="bg-white dark:bg-[#151E2E] rounded-lg p-3 border border-slate-200 dark:border-slate-800 text-sm text-slate-700 dark:text-slate-300 mb-2 shadow-sm prose prose-sm dark:prose-invert max-w-none">
                                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                            {step.content}
                                                        </ReactMarkdown>
                                                    </div>

                                                    {/* 工具调用详情 */}
                                                    {step.toolCalls && step.toolCalls.length > 0 && (
                                                        <div className="mt-3 space-y-2">
                                                            <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-2">
                                                                🔧 工具调用详情：
                                                            </div>
                                                            {step.toolCalls.map((toolCall: any) => (
                                                                <div
                                                                    key={toolCall.id}
                                                                    className="bg-white dark:bg-[#0F172A] rounded-lg p-3 border border-slate-200 dark:border-slate-700 text-xs"
                                                                >
                                                                    <div className="flex items-center justify-between mb-2">
                                                                        <span className="font-mono font-semibold text-[#3B82F6]">
                                                                            {toolCall.tool_name}
                                                                        </span>
                                                                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                                                            toolCall.status === 'success'
                                                                                ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                                                                                : toolCall.status === 'error'
                                                                                ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
                                                                                : 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400'
                                                                        }`}>
                                                                            {toolCall.status === 'success' ? '✅ 成功' :
                                                                             toolCall.status === 'error' ? '❌ 失败' : '⏳ 执行中'}
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
                                                                                <div className="mt-1 text-xs bg-slate-50 dark:bg-slate-900 p-2 rounded border border-slate-200 dark:border-slate-700 max-h-32 overflow-y-auto">
                                                                                    {toolCall.result}
                                                                                </div>
                                                                            </div>
                                                                        )}

                                                                        {toolCall.duration_ms && (
                                                                            <div className="text-xs text-slate-500">
                                                                                ⏱️ 耗时：{toolCall.duration_ms}ms
                                                                            </div>
                                                                        )}

                                                                        {toolCall.error && (
                                                                            <div className="text-xs text-red-600 dark:text-red-400">
                                                                                ⚠️ 错误：{toolCall.error}
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    )}
                                                </div>
                                            }
                                            isLast={index === msg.thinkingSteps.length - 1}
                                        />
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* 聊天气泡文本 */}
                <div className={`text-[15px] leading-relaxed ${msg.role === 'user'
                        ? 'bg-slate-100 dark:bg-[#2A2B32] text-slate-900 dark:text-slate-100 px-5 py-3.5 rounded-3xl'
                        : 'text-slate-800 dark:text-slate-200 py-1 prose prose-sm dark:prose-invert max-w-none'
                    }`}>
                    {msg.role === 'user' ? (
                        msg.content.split('\n').map((line: string, i: number) => (
                            <React.Fragment key={i}>
                                {line}
                                {i !== msg.content.split('\n').length - 1 && <div className="h-3"></div>}
                            </React.Fragment>
                        ))
                    ) : (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {msg.content}
                        </ReactMarkdown>
                    )}
                </div>

                {msg.role === 'assistant' && !hideFooter && (
                    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] font-medium text-slate-400">
                        {msg.mode === 'agent' ? (
                            <span className="flex items-center gap-1 text-emerald-500"><CheckCircle2 size={12} /> ReAct Agent 生成，数据已验证</span>
                        ) : (
                            <span className="flex items-center gap-1 text-amber-500"><AlertTriangle size={12} /> 原生 LLM 预测，未验证真实性</span>
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
                )}
            </div>
        </div>
    );
}

function ReactView({ showToast, selectedModel }: { showToast: (message: string, type?: string) => void; selectedModel?: string }) {
    const { steps, simulationState, errorMessage } = useReactStore();
    const { startTrace } = useReactTrace();
    const [inputText, setInputText] = useState('请帮我规划一个3天的杭州旅行，预算5000元，喜欢自然风光');
    const [maxRounds, setMaxRounds] = useState(3);
    const [expandedJson, setExpandedJson] = useState<Record<string, boolean>>({});
    const [showHistory, setShowHistory] = useState(false);

    useEffect(() => {
        fetchTravelSettings()
            .then((settings) => setMaxRounds(settings.max_rounds))
            .catch(() => {});
    }, []);

    const handleStart = () => {
        startTrace(inputText, maxRounds);
    };

    const toggleJson = (step: string) => {
        setExpandedJson(prev => ({ ...prev, [step]: !prev[step] }));
    };

    // 辅助函数
    const getIconForStepType = (type: string) => {
        switch (type) {
            case 'Observe': return <Search size={14} />
            case 'Think': return <Lightbulb size={14} />
            case 'Act': return <Code2 size={14} />
            case 'Verify': return <CheckCircle2 size={14} />
            default: return <Activity size={14} />
        }
    }

    const getColorForStepType = (type: string) => {
        switch (type) {
            case 'Observe': return 'blue'
            case 'Think': return 'purple'
            case 'Act': return 'orange'
            case 'Verify': return 'green'
            default: return 'blue'
        }
    }

    const getStepLabel = (type: string) => {
        const labels: Record<string, string> = {
            'Observe': '观察环境 (Observe)',
            'Think': '思考决策 (Think)',
            'Act': '执行动作 (Act)',
            'Verify': '观察结果 (Verify)'
        }
        return labels[type] || type
    }

    return (
        <div className="w-full flex flex-col animate-in fade-in slide-in-from-bottom-4 duration-500 pb-20">

            {/* 顶部控制栏 */}
            <div className="w-full mb-8 bg-white dark:bg-[#151E2E] p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
                <h2 className="text-2xl font-bold mb-1 tracking-tight">🧠 ReAct 推理链详解</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">深入查看 Agent 每一步的推理过程和工具调用</p>

                <div className="flex flex-col gap-4">
                    <div className="w-full relative shadow-sm rounded-lg flex items-center border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-[#0F172A] focus-within:ring-2 focus-within:ring-[#3B82F6]/50 focus-within:border-[#3B82F6] transition-all">
                        <input
                            type="text"
                            value={inputText}
                            onChange={(e) => setInputText(e.target.value)}
                            placeholder="输入你的任务..."
                            className="w-full py-3 pl-4 pr-4 bg-transparent border-none outline-none text-sm placeholder-slate-400"
                        />
                    </div>

                    <div className="flex flex-wrap items-center justify-between gap-4">
                        <div className="flex items-center gap-4">
                            <div className="flex items-center gap-2">
                                <ListFilter size={16} className="text-slate-400" />
                                <span className="text-xs font-medium text-slate-600 dark:text-slate-400">最大轮次</span>
                                <select
                                    value={maxRounds}
                                    onChange={(e) => setMaxRounds(Number(e.target.value))}
                                    className="bg-slate-50 dark:bg-[#0F172A] border border-slate-200 dark:border-slate-700 rounded-md px-2 py-1.5 text-xs outline-none focus:border-[#3B82F6]"
                                >
                                    {[1, 2, 3, 4, 5].map(n => <option key={n} value={n}>{n}</option>)}
                                </select>
                            </div>
                            <div className="flex items-center gap-2">
                                <Brain size={16} className="text-slate-400" />
                                <span className="text-xs font-medium text-slate-600 dark:text-slate-400">模型</span>
                                <div className="bg-slate-50 dark:bg-[#0F172A] border border-slate-200 dark:border-slate-700 rounded-md px-3 py-1.5 text-xs text-slate-700 dark:text-slate-300">
                                    {selectedModel || '未配置模型'}
                                </div>
                            </div>
                        </div>

                        <button
                            onClick={handleStart}
                            disabled={simulationState === 'loading'}
                            className="flex items-center gap-2 px-6 py-2 bg-[#3B82F6] hover:bg-[#2563EB] text-white text-sm font-medium rounded-lg transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            <Play size={16} fill="currentColor" />
                            开始推理
                        </button>
                    </div>
                </div>
            </div>

            {/* 主体：全宽 ReAct 时间线 */}
            {simulationState === 'idle' && (
                <EmptyState
                    icon={Activity}
                    title="等待执行追踪"
                    description="点击上方的「开始推理」按钮，查看详细的 Agent 执行过程、决策树以及 API 调用详情。"
                />
            )}

            {/* 动态渲染 ReAct 步骤（loading 和 done 状态都显示） */}
            {(simulationState === 'loading' || simulationState === 'done') && steps.length > 0 && (
                <div className="w-full bg-white dark:bg-[#151E2E] rounded-xl border border-slate-200 dark:border-slate-800 p-8 shadow-sm">
                    <h3 className="text-lg font-semibold mb-6 flex items-center gap-2">
                        <Activity size={20} className="text-[#3B82F6]" />
                        执行追踪 (Trace)
                        {simulationState === 'loading' && (
                            <span className="ml-2 text-sm font-normal text-slate-500 dark:text-slate-400 flex items-center gap-2">
                                <Loader2 size={16} className="animate-spin" />
                                执行中...
                            </span>
                        )}
                    </h3>

                    <div className="pl-2 relative max-w-4xl mx-auto">
                        <div className="absolute left-[19px] top-2 bottom-0 w-[2px] bg-slate-100 dark:bg-slate-800 z-0"></div>

                        {steps.map((step, index) => (
                            <TimelineStep
                                key={step.sequence}
                                icon={getIconForStepType(step.type)}
                                color={getColorForStepType(step.type)}
                                label={`${index + 1}. ${getStepLabel(step.type)}`}
                                content={
                                    <div className="w-full">
                                        <div className="bg-slate-50 dark:bg-[#0F172A] rounded-lg p-3 border border-slate-200 dark:border-slate-800 text-sm text-slate-700 dark:text-slate-300 mb-2 shadow-sm prose prose-sm dark:prose-invert max-w-none">
                                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                {step.content}
                                            </ReactMarkdown>
                                        </div>

                                        {/* 工具调用详情 */}
                                        {step.toolCalls && step.toolCalls.length > 0 && (
                                            <div className="mt-3 space-y-2">
                                                <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-2">
                                                    🔧 工具调用详情：
                                                </div>
                                                {step.toolCalls.map((toolCall) => (
                                                    <div
                                                        key={toolCall.id}
                                                        className="bg-white dark:bg-[#0F172A] rounded-lg p-3 border border-slate-200 dark:border-slate-700 text-xs"
                                                    >
                                                        <div className="flex items-center justify-between mb-2">
                                                            <span className="font-mono font-semibold text-[#3B82F6]">
                                                                {toolCall.tool_name}
                                                            </span>
                                                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                                                toolCall.status === 'success'
                                                                    ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                                                                    : toolCall.status === 'error'
                                                                    ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
                                                                    : 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400'
                                                            }`}>
                                                                {toolCall.status === 'success' ? '✅ 成功' :
                                                                 toolCall.status === 'error' ? '❌ 失败' : '⏳ 执行中'}
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
                                                                    <div className="mt-1 text-xs bg-slate-50 dark:bg-slate-900 p-2 rounded border border-slate-200 dark:border-slate-700 max-h-32 overflow-y-auto">
                                                                        {toolCall.result}
                                                                    </div>
                                                                </div>
                                                            )}

                                                            {toolCall.duration_ms && (
                                                                <div className="text-xs text-slate-500">
                                                                    ⏱️ 耗时：{toolCall.duration_ms}ms
                                                                </div>
                                                            )}

                                                            {toolCall.error && (
                                                                <div className="text-xs text-red-600 dark:text-red-400">
                                                                    ⚠️ 错误：{toolCall.error}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                }
                                isLast={index === steps.length - 1}
                            />
                        ))}
                    </div>
                </div>
            )}

            {/* 新增：错误状态显示 */}
            {simulationState === 'error' && errorMessage && (
                <div className="w-full bg-red-50 dark:bg-red-900/20 rounded-xl border border-red-200 dark:border-red-800 p-6">
                    <div className="flex items-start gap-3">
                        <AlertCircle size={24} className="text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
                        <div className="flex-1">
                            <h3 className="text-lg font-semibold text-red-800 dark:text-red-300 mb-2">
                                执行失败
                            </h3>
                            <p className="text-sm text-red-700 dark:text-red-400 mb-4">
                                {errorMessage}
                            </p>
                            <button
                                onClick={() => useReactStore.getState().reset()}
                                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition-colors"
                            >
                                重新开始
                            </button>
                        </div>
                    </div>
                </div>
            )}

        </div>
    );
}

function ToolsView({ showToast }: { showToast: (message: string, type?: string) => void }) {
    // ✅ 使用真实 API 加载工具列表
    const [toolsList, setToolsList] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [copiedId, setCopiedId] = useState<string | null>(null);
    const [selectedTool, setSelectedTool] = useState<any>(null);
    const [testParams, setTestParams] = useState<Record<string, any>>({});
    const [testResult, setTestResult] = useState<string | null>(null);
    const [isExecuting, setIsExecuting] = useState(false);

    // ✅ 加载工具列表
    useEffect(() => {
        fetchToolsList()
            .then(tools => {
                const formattedTools = tools.map(tool => ({
                    id: tool.name,
                    name: tool.name,
                    desc: tool.description,
                    icon: getIconForTool(tool.name),
                    enabled: true,
                    displaySchema: formatSchemaForDisplay(tool.parameters),
                    schema: tool.parameters
                }));
                setToolsList(formattedTools);
                setLoading(false);
            })
            .catch(error => {
                console.error('Failed to fetch tools:', error);
                showToast('工具列表加载失败', 'error');
                setLoading(false);
            });
    }, []);

    const getIconForTool = (name: string) => {
        const iconMap: Record<string, any> = {
            'get_weather': CloudSun,
            'search_attractions': Landmark,
            'search_hotels': Building2,
            'search_transport': Train,
            'search_food_recommendations': UtensilsCrossed,
            'calculate': Calculator
        };
        return iconMap[name] || Code2;
    };

    const formatSchemaForDisplay = (parameters: any) => {
        const props = parameters.properties || {};
        const required = parameters.required || [];
        const displayObj: Record<string, string> = {};

        Object.keys(props).forEach(key => {
            const isRequired = required.includes(key);
            displayObj[`${key}${isRequired ? '' : '?'}`] = props[key].type;
        });

        return JSON.stringify(displayObj, null, 2);
    };

    const handleCopy = (id: string, text: string) => {
        navigator.clipboard.writeText(text);
        setCopiedId(id);
        showToast('Schema 复制成功', 'success');
        setTimeout(() => setCopiedId(null), 2000);
    };

    const toggleToolStatus = (id: string) => {
        setToolsList(prev => prev.map(t => t.id === id ? { ...t, enabled: !t.enabled } : t));
    };

    const openTestPanel = (tool: any) => {
        if (!tool.enabled) return;
        setSelectedTool(tool);
        setTestParams({});
        setTestResult(null);
    };

    const closeTestPanel = () => {
        setSelectedTool(null);
    };

    const handleExecute = async () => {
        if (!selectedTool) return;
        setIsExecuting(true);
        setTestResult(null);
        try {
            const result = await testTool(selectedTool.name, testParams);
            setTestResult(JSON.stringify(result, null, 2));
            showToast('工具调用成功', 'success');
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            setTestResult(JSON.stringify({ ok: false, tool_name: selectedTool.name, error: message }, null, 2));
            showToast(`工具调用失败: ${message}`, 'error');
        } finally {
            setIsExecuting(false);
        }
    };

    const enabledCount = toolsList.filter(t => t.enabled).length;

    if (loading) {
        return (
            <div className="w-full flex items-center justify-center py-20">
                <Loader2 size={32} className="animate-spin text-[#3B82F6]" />
            </div>
        );
    }

    return (
        <div className="w-full max-w-5xl flex flex-col animate-in fade-in slide-in-from-bottom-4 duration-500 pb-20 relative">

            {/* 顶部标题区 */}
            <div className="flex items-center justify-between mb-8 bg-white dark:bg-[#151E2E] p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
                <div>
                    <h2 className="text-2xl font-bold mb-1 tracking-tight">🔧 工具注册表</h2>
                    <p className="text-sm text-slate-500 dark:text-slate-400">查看 Agent 可以使用的所有工具，理解 Function Calling 的 JSON Schema</p>
                </div>
                <div className="flex items-center gap-4">
                    <div className="text-sm font-medium px-4 py-2 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-lg border border-slate-200 dark:border-slate-700 shadow-sm">
                        共 <span className="text-[#3B82F6] font-bold">{enabledCount}</span> 个工具可用
                    </div>
                </div>
            </div>

            {/* 主体：工具卡片网格 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {toolsList.map((tool) => {
                    const Icon = tool.icon;
                    return (
                        <div key={tool.id} className={`bg-white dark:bg-[#151E2E] rounded-xl border flex flex-col shadow-sm transition-all duration-300 overflow-hidden group ${tool.enabled ? 'border-slate-200 dark:border-slate-800 hover:shadow-md' : 'border-slate-200 dark:border-slate-800 opacity-60 grayscale-[30%]'}`}>

                            {/* 卡片上部：基本信息 */}
                            <div className="p-5 border-b border-slate-100 dark:border-slate-800/60 flex flex-col gap-3">
                                <div className="flex items-start justify-between gap-3">
                                    <div className="flex items-center gap-3 min-w-0 flex-1">
                                        <div className={`w-10 h-10 shrink-0 rounded-lg bg-slate-100 dark:bg-[#0F172A] flex items-center justify-center border border-slate-200 dark:border-slate-700 transition-colors ${tool.enabled ? 'text-slate-600 dark:text-slate-400 group-hover:text-[#3B82F6] group-hover:border-[#3B82F6]/30' : 'text-slate-400 dark:text-slate-600'}`}>
                                            <Icon size={20} />
                                        </div>
                                        <h3
                                            className={`font-mono text-sm font-bold leading-snug break-all ${tool.enabled ? 'text-slate-800 dark:text-slate-200' : 'text-slate-500 dark:text-slate-500'}`}
                                            title={tool.name}
                                        >
                                            {tool.name}
                                        </h3>
                                    </div>

                                    {/* 状态切换 Toggle 开关 */}
                                    <div className="flex items-center gap-2 shrink-0 pt-0.5">
                                        <span className={`text-xs font-medium whitespace-nowrap ${tool.enabled ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400'}`}>
                                            {tool.enabled ? '已启用' : '已停用'}
                                        </span>
                                        <button
                                            type="button"
                                            role="switch"
                                            aria-checked={tool.enabled}
                                            aria-label={tool.enabled ? '停用工具' : '启用工具'}
                                            onClick={() => toggleToolStatus(tool.id)}
                                            className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40 ${tool.enabled ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-700'}`}
                                        >
                                            <span className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${tool.enabled ? 'translate-x-4' : 'translate-x-0'}`} />
                                        </button>
                                    </div>
                                </div>
                                <p className="text-sm text-slate-500 dark:text-slate-400 leading-relaxed min-h-[40px]">
                                    {tool.desc}
                                </p>
                            </div>

                            {/* 卡片中部：Schema 展示 */}
                            <div className="p-5 bg-slate-50 dark:bg-[#0F172A] flex-1">
                                <div className="text-xs font-semibold text-slate-600 dark:text-slate-400 mb-2.5 flex items-center gap-1.5">
                                    <FileJson size={14} className="shrink-0" />
                                    <span>参数定义 (JSON Schema)</span>
                                </div>
                                <pre className="text-xs leading-relaxed text-slate-700 dark:text-slate-300 font-mono bg-white dark:bg-[#151E2E] p-3.5 rounded-lg border border-slate-200 dark:border-slate-700 overflow-x-auto m-0">
                                    {tool.displaySchema}
                                </pre>
                            </div>

                            {/* 卡片底部：操作按钮 */}
                            <div className="p-4 border-t border-slate-200 dark:border-slate-800 flex gap-3 bg-white dark:bg-[#151E2E]">
                                <button
                                    type="button"
                                    onClick={() => handleCopy(tool.id, tool.displaySchema)}
                                    className="flex-1 flex items-center justify-center gap-1.5 py-2.5 px-3 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-sm font-medium rounded-lg transition-colors border border-slate-200 dark:border-slate-700"
                                >
                                    {copiedId === tool.id ? <Check size={15} className="text-emerald-500 shrink-0" /> : <Copy size={15} className="shrink-0" />}
                                    <span className="truncate">{copiedId === tool.id ? '已复制' : '复制 Schema'}</span>
                                </button>
                                <button
                                    type="button"
                                    onClick={() => openTestPanel(tool)}
                                    disabled={!tool.enabled}
                                    className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 px-3 text-sm font-medium rounded-lg transition-colors shadow-sm
                  ${tool.enabled
                                            ? 'bg-[#3B82F6] hover:bg-[#2563EB] text-white'
                                            : 'bg-slate-200 dark:bg-slate-800 text-slate-400 cursor-not-allowed shadow-none'
                                        }`}
                                >
                                    <Play size={15} fill={tool.enabled ? 'currentColor' : 'none'} className={`shrink-0 ${tool.enabled ? 'opacity-90' : ''}`} />
                                    <span className="truncate">测试调用</span>
                                </button>
                            </div>

                        </div>
                    );
                })}
            </div>

            {/* 测试面板遮罩层 */}
            {selectedTool && (
                <div
                    className="fixed inset-0 bg-black/20 dark:bg-black/40 z-40 transition-opacity backdrop-blur-sm"
                    onClick={closeTestPanel}
                ></div>
            )}

            {/* 右侧滑出测试面板 (Drawer) */}
            <div className={`fixed top-0 right-0 h-full w-[400px] bg-white dark:bg-[#0F172A] shadow-[-10px_0_30px_rgba(0,0,0,0.15)] border-l border-slate-200 dark:border-slate-800 transition-transform duration-300 z-50 flex flex-col ${selectedTool ? 'translate-x-0' : 'translate-x-full'}`}>

                {selectedTool && (
                    <>
                        {/* Drawer 头部 */}
                        <div className="h-16 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-6 bg-slate-50 dark:bg-[#151E2E]">
                            <div className="flex items-center gap-2">
                                {React.createElement(selectedTool.icon, { size: 18, className: "text-[#3B82F6]" })}
                                <h3 className="font-bold text-slate-800 dark:text-slate-200 font-mono tracking-tight">测试 {selectedTool.name}</h3>
                            </div>
                            <button
                                onClick={closeTestPanel}
                                className="p-1.5 rounded-md text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors"
                            >
                                <X size={18} />
                            </button>
                        </div>

                        {/* Drawer 滚动内容 */}
                        <div className="flex-1 overflow-y-auto p-6 flex flex-col">

                            <div className="text-sm text-slate-500 dark:text-slate-400 mb-6 bg-blue-50 dark:bg-blue-500/10 p-3 rounded-lg border border-blue-100 dark:border-blue-500/20">
                                请填写下方参数以模拟 Tool API 的真实调用过程。
                            </div>

                            {/* 动态输入表单 */}
                            <div className="space-y-4 mb-6">
                                {selectedTool.schema.properties && Object.entries(selectedTool.schema.properties).map(([key, prop]: [string, any]) => {
                                    const isRequired = selectedTool.schema.required?.includes(key);
                                    return (
                                        <div key={key}>
                                            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5 flex items-center gap-1">
                                                {key}
                                                {isRequired ? <span className="text-red-500 font-bold">*</span> : <span className="text-slate-400 text-[10px] font-normal tracking-wide uppercase">(Optional)</span>}
                                            </label>
                                            <input
                                                type={prop.type === 'number' ? 'number' : 'text'}
                                                placeholder={prop.description || ''}
                                                value={testParams[key] || ''}
                                                onChange={(e) => setTestParams({ ...testParams, [key]: prop.type === 'number' ? Number(e.target.value) : e.target.value })}
                                                className="w-full py-2 px-3 text-sm bg-white dark:bg-[#151E2E] border border-slate-300 dark:border-slate-700 rounded-lg outline-none focus:border-[#3B82F6] focus:ring-2 focus:ring-[#3B82F6]/20 transition-all text-slate-800 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-600 shadow-sm"
                                            />
                                        </div>
                                    );
                                })}
                            </div>

                            {/* 执行按钮 */}
                            <button
                                onClick={handleExecute}
                                disabled={isExecuting}
                                className={`w-full py-3 rounded-lg text-sm font-bold shadow-sm flex items-center justify-center gap-2 transition-all
                  ${isExecuting
                                        ? 'bg-slate-100 dark:bg-slate-800 text-slate-400 cursor-not-allowed border border-slate-200 dark:border-slate-700'
                                        : 'bg-[#3B82F6] hover:bg-[#2563EB] text-white hover:shadow-md'
                                    }`}
                            >
                                {isExecuting ? <Loader2 size={18} className="animate-spin" /> : <Play size={18} fill="currentColor" className="opacity-90" />}
                                {isExecuting ? '处理中...' : '执 行'}
                            </button>

                            {/* 结果展示区 */}
                            {testResult && (
                                <div className="mt-8 animate-in fade-in slide-in-from-bottom-2 duration-300">
                                    <div className="text-xs font-semibold text-emerald-600 dark:text-emerald-500 mb-2 flex items-center gap-1.5 uppercase tracking-wider">
                                        <CheckCircle2 size={14} /> Execution Result
                                    </div>
                                    <pre className="text-sm text-emerald-800 dark:text-emerald-300 font-mono bg-emerald-50 dark:bg-[#0A1A12] p-4 rounded-lg border border-emerald-100 dark:border-emerald-900/50 shadow-inner overflow-x-auto">
                                        {testResult}
                                    </pre>
                                </div>
                            )}
                        </div>
                    </>
                )}
            </div>

        </div>
    );
}

function SettingsView({ showToast, onOpenModelSettings }: { showToast: (message: string, type?: string) => void; onOpenModelSettings?: () => void }) {
    const [settings, setSettings] = useState<TravelSettings | null>(null);
    const [loading, setLoading] = useState(true);
    const [maxRounds, setMaxRounds] = useState(3);

    useEffect(() => {
        fetchTravelSettings()
            .then((data) => {
                setSettings(data);
                setMaxRounds(data.max_rounds);
                setLoading(false);
            })
            .catch((error) => {
                console.error('Failed to fetch travel settings:', error);
                showToast('配置加载失败', 'error');
                setLoading(false);
            });
    }, []);

    const handleSave = async () => {
        try {
            await updateTravelSettings({ max_rounds: maxRounds });
            showToast('Agent 参数已保存', 'success');
        } catch (error) {
            console.error('Failed to save travel settings:', error);
            showToast('保存失败', 'error');
        }
    };

    if (loading) {
        return (
            <div className="w-full flex items-center justify-center py-20">
                <Loader2 size={32} className="animate-spin text-[#3B82F6]" />
            </div>
        );
    }

    if (!settings) {
        return (
            <div className="w-full flex items-center justify-center py-20">
                <div className="text-center">
                    <AlertCircle size={48} className="text-red-500 mx-auto mb-4" />
                    <p className="text-slate-600 dark:text-slate-400">配置加载失败</p>
                </div>
            </div>
        );
    }

    return (
        <div className="w-full max-w-[640px] mx-auto flex flex-col animate-in fade-in slide-in-from-bottom-4 duration-500 pb-20 relative">
            <div className="mb-8">
                <h2 className="text-3xl font-bold mb-2 tracking-tight">⚙️ 旅行 Agent 设置</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">LLM 模型请在主工作台「设置」中配置；此处管理 Agent 推理参数与外部工具状态</p>
            </div>

            <div className="space-y-6">
                <div className="bg-white dark:bg-[#151E2E] p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
                    <h3 className="text-sm font-bold mb-4 text-slate-800 dark:text-slate-200 flex items-center gap-2">
                        <Brain size={16} className="text-[#3B82F6]" /> 模型连接
                    </h3>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
                        旅行 Agent 复用 Qi 的 AI Studio 的模型配置（BYOK），与主聊天工作台共用同一套 API Key。
                    </p>
                    {onOpenModelSettings && (
                        <button
                            onClick={onOpenModelSettings}
                            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-[#3B82F6] border border-[#3B82F6]/30 rounded-lg hover:bg-[#3B82F6]/5"
                        >
                            <Plug size={16} /> 打开模型连接设置
                        </button>
                    )}
                </div>

                <div className="bg-white dark:bg-[#151E2E] p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
                    <h3 className="text-sm font-bold mb-4 text-slate-800 dark:text-slate-200">ReAct 推理轮次</h3>
                    <input
                        type="number"
                        min={1}
                        max={10}
                        value={maxRounds}
                        onChange={(e) => setMaxRounds(Number(e.target.value))}
                        className="w-full py-2.5 px-3 text-sm bg-slate-50 dark:bg-[#0F172A] border border-slate-200 dark:border-slate-700 rounded-lg"
                    />
                </div>

                <div className="bg-white dark:bg-[#151E2E] p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
                    <h3 className="text-sm font-bold mb-4 text-slate-800 dark:text-slate-200">外部工具（服务端 .env）</h3>
                    <ul className="space-y-2 text-sm">
                        <li className="flex items-center gap-2">
                            {settings.amap_api_key ? <CheckCircle2 size={16} className="text-emerald-500" /> : <AlertTriangle size={16} className="text-amber-500" />}
                            高德地图 AMAP_API_KEY {settings.amap_api_key ? '已配置' : '未配置'}
                        </li>
                        <li className="flex items-center gap-2">
                            {settings.tavily_api_key ? <CheckCircle2 size={16} className="text-emerald-500" /> : <AlertTriangle size={16} className="text-amber-500" />}
                            Tavily TAVILY_API_KEY {settings.tavily_api_key ? '已配置' : '未配置'}
                        </li>
                        <li className="flex items-center gap-2">
                            {settings.juhe_train_api_key ? <CheckCircle2 size={16} className="text-emerald-500" /> : <AlertTriangle size={16} className="text-amber-500" />}
                            聚合数据 JUHE_TRAIN_API_KEY {settings.juhe_train_api_key ? '已配置' : '未配置'}
                        </li>
                        <li className="flex items-center gap-2">
                            {settings.juhe_flight_api_key ? <CheckCircle2 size={16} className="text-emerald-500" /> : <AlertTriangle size={16} className="text-amber-500" />}
                            聚合数据 JUHE_FLIGHT_API_KEY {settings.juhe_flight_api_key ? '已配置' : '未配置'}
                        </li>
                    </ul>
                </div>

                <div className="flex justify-end pt-4">
                    <button
                        onClick={handleSave}
                        className="flex items-center gap-2 px-8 py-2.5 bg-[#3B82F6] hover:bg-[#2563EB] text-white text-sm font-bold rounded-lg transition-colors shadow-md shadow-blue-500/20"
                    >
                        <Save size={16} /> 保存 Agent 参数
                    </button>
                </div>
            </div>
        </div>
    );
}

/* ================= 辅助组件 ================= */

// 时间线步骤组件
function TimelineStep({ icon, color, label, content, isLast }: {
    icon: React.ReactNode;
    color: string;
    label: string;
    content: React.ReactNode;
    isLast: boolean;
}) {
    const colorMap: Record<string, string> = {
        blue: 'bg-blue-500',
        purple: 'bg-purple-500',
        orange: 'bg-orange-500',
        green: 'bg-emerald-500'
    };

    return (
        <div className={`relative pl-8 ${isLast ? '' : 'pb-8'}`}>
            <div className={`absolute left-0 top-1.5 w-6 h-6 rounded-full ${colorMap[color] || 'bg-blue-500'} flex items-center justify-center text-white shadow-sm ring-4 ring-white dark:ring-[#151E2E] z-10`}>
                {icon}
            </div>
            <div className="mb-2">
                <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">{label}</span>
            </div>
            <div>{content}</div>
        </div>
    );
}

// Toast 通知组件
function Toast({ message, type, onClose }: {
    message: string;
    type: string;
    onClose: () => void;
}) {
    useEffect(() => {
        const timer = setTimeout(onClose, 3000);
        return () => clearTimeout(timer);
    }, [onClose]);

    const bgColor = type === 'success' ? 'bg-emerald-500' : type === 'error' ? 'bg-red-500' : 'bg-blue-500';

    return (
        <div className={`fixed top-4 right-4 ${bgColor} text-white px-6 py-3 rounded-lg shadow-lg z-50 animate-in slide-in-from-top-2 duration-300`}>
            <div className="flex items-center gap-2">
                {type === 'success' && <CheckCircle2 size={18} />}
                {type === 'error' && <AlertTriangle size={18} />}
                <span className="text-sm font-medium">{message}</span>
            </div>
        </div>
    );
}

// 空状态组件
function EmptyState({ icon: Icon, title, description }: {
    icon: any;
    title: string;
    description: string;
}) {
    return (
        <div className="w-full bg-white dark:bg-[#151E2E] rounded-xl border border-slate-200 dark:border-slate-800 p-12 shadow-sm flex flex-col items-center justify-center text-center">
            <div className="w-16 h-16 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center mb-4">
                <Icon size={32} className="text-slate-400" />
            </div>
            <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-300 mb-2">{title}</h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 max-w-md">{description}</p>
        </div>
    );
}

// 骨架屏加载组件
function SkeletonPulse({ className }: { className?: string }) {
    return (
        <div className={`bg-slate-200 dark:bg-slate-700 rounded animate-pulse ${className || ''}`}></div>
    );
}
