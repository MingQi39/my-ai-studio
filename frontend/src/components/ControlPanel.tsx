import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Settings2, Zap, Globe, Terminal, Code, FileJson, ChevronRight, FileCode } from 'lucide-react';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { cn } from '@/components/ui/utils';
import { toast } from 'sonner';
import { SystemInstructionModal } from '@/components/SystemInstructionModal';
import { SystemInstructionResponse } from '@/services/api';

export type ChatToolsState = {
  search: boolean;
  code: boolean;
  function: boolean;
  structured: boolean;
};

export const DEFAULT_CHAT_TOOLS_STATE: ChatToolsState = {
  search: false,
  code: false,
  function: false,
  structured: false,
};

/** 主工作台工具开关 */
export const CHAT_TOOLS_AVAILABLE = true;

interface ControlPanelProps {
  onModelClick: () => void;
  selectedModel: string;
  isDarkMode: boolean;
  enableReasoning: boolean;
  onEnableReasoningChange: (enabled: boolean) => void;
  currentInstruction: SystemInstructionResponse | null;
  onInstructionChange: (instruction: SystemInstructionResponse | null) => void;
  // 临时输入的系统指令（用户直接在文本框中输入的）
  tempSystemPrompt: string;
  onTempSystemPromptChange: (prompt: string) => void;
  // 面板展开/收起
  isOpen?: boolean;
  togglePanel?: () => void;
  toolsState: ChatToolsState;
  onToolsStateChange: (state: ChatToolsState) => void;
}

export function ControlPanel({
  onModelClick,
  selectedModel,
  isDarkMode,
  enableReasoning,
  onEnableReasoningChange,
  currentInstruction,
  onInstructionChange,
  tempSystemPrompt,
  onTempSystemPromptChange,
  isOpen = true,
  togglePanel,
  toolsState,
  onToolsStateChange,
}: ControlPanelProps) {
  const { t } = useTranslation();
  const [temperature, setTemperature] = useState([0.8]);
  const [topP, setTopP] = useState([0.95]);
  const [outputLength, setOutputLength] = useState(8192);
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);

  // 系统提示词模态框状态
  const [isInstructionModalOpen, setIsInstructionModalOpen] = useState(false);

  const handleSettingsClick = () => {
    toast.info(t('controlPanel.openGlobalSettings'));
  };

  const handleTempInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    if (!isNaN(val) && val >= 0 && val <= 2) {
      setTemperature([val]);
    }
  };

  const handleSelectInstruction = (instruction: SystemInstructionResponse) => {
    onInstructionChange(instruction);
    toast.success(t('controlPanel.instructionSelected', { title: instruction.title }));
  };

  return (

    <div className="w-full md:w-[300px] h-full flex flex-col bg-[var(--bg-panel)] border-l border-[var(--border-color)] flex-shrink-0 text-[var(--text-primary)] font-sans overflow-y-auto custom-scrollbar transition-colors duration-300">
      {/* Header */}
      <div className="h-[60px] flex items-center justify-between px-5 border-b border-[var(--border-color)] flex-shrink-0">
        <h2 className="font-semibold text-sm">{t('controlPanel.runSettings')}</h2>
        <Settings2
          size={16}
          className="text-[var(--text-secondary)] cursor-pointer hover:text-[var(--text-primary)] transition-colors"
          onClick={togglePanel}
        />
      </div>

      <div className="p-5 flex flex-col gap-6">

        {/* 1. Model Selection */}
        <div className="flex flex-col gap-3">
          <Label className="text-sm font-medium text-[var(--text-primary)]">{t('controlPanel.applyModel')}</Label>
          <div
            onClick={onModelClick}
            className={cn(
              'group relative rounded-xl p-4 cursor-pointer transition-all duration-200 border shadow-sm',
              isDarkMode ? 'bg-[#1E1F20] border-[#27272a]' : 'bg-white border-[var(--border-color)]',
              'hover:border-blue-300 dark:hover:border-blue-400/40',
            )}
          >
            <div className="flex justify-between items-start">
              <div className="overflow-hidden flex flex-col gap-1 min-w-0">
                <div className="font-mono text-[10px] text-[var(--text-secondary)] truncate">
                  {selectedModel ? selectedModel.toLowerCase().replace(/\s+/g, '-') : '—'}
                </div>
                <h3
                  className="text-[var(--text-primary)] font-bold text-sm truncate pr-2"
                  title={selectedModel || undefined}
                >
                  {selectedModel || t('controlPanel.selectModel')}
                </h3>
              </div>
              <Zap size={18} className="text-blue-500 fill-blue-500 flex-shrink-0" />
            </div>
          </div>
        </div>

        <div className="h-px bg-[var(--border-color)]" />

        {/* 2. System Instructions */}
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <Label className="text-sm font-medium text-[var(--text-primary)]">{t('controlPanel.instructionLabel')}</Label>
            <button
              onClick={() => setIsInstructionModalOpen(true)}
              className="flex items-center gap-1 px-2 py-1 text-xs text-blue-500 hover:text-blue-600 hover:bg-blue-500/10 rounded transition-colors"
            >
              <FileCode size={12} />
              {t('common.manage')}
            </button>
          </div>

          {currentInstruction ? (
            <div className="p-3 rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-[var(--text-primary)]">{currentInstruction.title}</span>
                <button
                  onClick={() => onInstructionChange(null)}
                  className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] text-xs"
                >
                  {t('common.clear')}
                </button>
              </div>
              <p className="text-xs text-[var(--text-secondary)] line-clamp-3">
                {currentInstruction.content}
              </p>
            </div>
          ) : (
            <Textarea
              value={tempSystemPrompt}
              onChange={(e) => onTempSystemPromptChange(e.target.value)}
              placeholder={t('controlPanel.instructionPlaceholder')}
              className={cn(
                "border-[var(--border-color)] rounded-lg text-sm min-h-[120px] resize-none focus-visible:ring-1 focus-visible:ring-blue-500/50 placeholder:text-[var(--text-placeholder)]",
                isDarkMode ? "bg-[#09090b] text-gray-200 border-[#27272a]" : "bg-[var(--bg-input)]"
              )}
            />
          )}
        </div>


        {/* 3. Parameters */}
        <div className="flex flex-col gap-5">
          <Label className="text-sm font-medium text-[var(--text-primary)]">{t('controlPanel.params')}</Label>

          {/* A. Temperature */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-[var(--text-primary)]">{t('controlPanel.temperature')}</span>
            </div>
            <div className="flex items-center gap-3">
              <Slider
                value={temperature}
                onValueChange={setTemperature}
                max={2}
                step={0.1}
                className="flex-1 py-2"
              />
              <div className={cn(
                "w-[48px] h-[32px] flex items-center justify-center border rounded-md overflow-hidden",
                // User requested "Light Black" (meaning a clean dark surface, likely darker/cleaner than the previous gray)
                isDarkMode ? "bg-[#09090b] border-[#27272a]" : "bg-[var(--bg-input)] border-[var(--border-color)]"
              )}>
                <input
                  type="number"
                  value={temperature[0]}
                  onChange={handleTempInputChange}
                  step={0.1}
                  max={2}
                  min={0}
                  className="w-full h-full bg-transparent text-center text-xs font-mono text-[var(--text-primary)] focus:outline-none"
                />
              </div>
            </div>
          </div>

          {/* B. Thinking Level */}
          <div className="flex flex-col gap-2">
            <span className="text-sm text-[var(--text-primary)]">{t('controlPanel.thinkingLevel')}</span>
            <Select defaultValue="high">
              <SelectTrigger className={cn(
                "w-full text-xs h-9 rounded-md text-[var(--text-primary)] focus:ring-1 focus:ring-blue-500/50",
                isDarkMode ? "bg-[#09090b] border-[#27272a]" : "bg-[var(--bg-input)] border-[var(--border-color)]"
              )}>
                <SelectValue placeholder={t('controlPanel.selectLevel')} />
              </SelectTrigger>
              <SelectContent className="bg-[var(--bg-card)] border-[var(--border-color)] text-[var(--text-primary)]">
                <SelectItem value="high">{t('controlPanel.high')}</SelectItem>
                <SelectItem value="medium">{t('controlPanel.medium')}</SelectItem>
                <SelectItem value="low">{t('controlPanel.low')}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* C. Reasoning Mode Toggle */}
          <div className="flex items-center justify-between group cursor-pointer" onClick={() => onEnableReasoningChange(!enableReasoning)}>
            <div className="flex flex-col gap-1">
              <span className="text-sm text-[var(--text-primary)]">{t('controlPanel.reasoningMode')}</span>
              <span className="text-xs text-[var(--text-secondary)]">
                {enableReasoning ? t('controlPanel.reasoningOn') : t('controlPanel.reasoningOff')}
              </span>
            </div>
            <Switch
              checked={enableReasoning}
              onCheckedChange={onEnableReasoningChange}
              className="data-[state=checked]:bg-blue-600"
            />
          </div>
        </div>

        <div className="h-px bg-[var(--border-color)]" />

        {/* 4. Tools */}
        <div className="flex flex-col gap-4">
          <Label className="text-sm font-medium text-[var(--text-primary)]">{t('controlPanel.tools')}</Label>

          <ToolToggle
            icon={<Globe size={16} />}
            label={t('controlPanel.googleSearch')}
            checked={toolsState.search}
            disabled={!CHAT_TOOLS_AVAILABLE}
            onCheckedChange={(c) => onToolsStateChange({ ...toolsState, search: c })}
          />
          <ToolToggle
            icon={<Terminal size={16} />}
            label={t('controlPanel.codeExec')}
            checked={toolsState.code}
            disabled={!CHAT_TOOLS_AVAILABLE}
            onCheckedChange={(c) => onToolsStateChange({ ...toolsState, code: c })}
          />
          <ToolToggle
            icon={<Code size={16} />}
            label={t('controlPanel.functionCall')}
            checked={toolsState.function}
            disabled={!CHAT_TOOLS_AVAILABLE}
            onCheckedChange={(c) => onToolsStateChange({ ...toolsState, function: c })}
          />
          <ToolToggle
            icon={<FileJson size={16} />}
            label={t('controlPanel.structuredOutput')}
            checked={toolsState.structured}
            disabled={!CHAT_TOOLS_AVAILABLE}
            onCheckedChange={(c) => onToolsStateChange({ ...toolsState, structured: c })}
          />
        </div>

        {/* 5. Advanced */}
        <Collapsible open={isAdvancedOpen} onOpenChange={setIsAdvancedOpen} className="border-t border-[var(--border-color)] pt-4">
          <CollapsibleTrigger className="flex items-center gap-2 text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors w-full group select-none">
            <ChevronRight size={14} className={cn("transition-transform duration-200", isAdvancedOpen && "rotate-90")} />
            <span>{t('controlPanel.advanced')}</span>
          </CollapsibleTrigger>

          <CollapsibleContent className="pt-4 space-y-5">
            {/* Top P */}
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-[var(--text-primary)]">Top P</span>
                <span className="text-xs font-mono text-[var(--text-secondary)]">{topP[0]}</span>
              </div>
              <Slider
                value={topP}
                onValueChange={setTopP}
                max={1}
                step={0.05}
              />
            </div>

            {/* Output Length */}
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-[var(--text-primary)]">{t('controlPanel.outputLength')}</span>
              </div>
              <Input
                type="number"
                value={outputLength}
                onChange={(e) => setOutputLength(Number(e.target.value))}
                className={cn(
                  "h-8 text-xs font-mono text-[var(--text-primary)] focus-visible:ring-1 focus-visible:ring-blue-500/50",
                  isDarkMode ? "bg-[#161718] border-[#333]" : "bg-[var(--bg-input)] border-[var(--border-color)]"
                )}
              />
            </div>
          </CollapsibleContent>
        </Collapsible>

      </div>

      {/* System Instruction Modal */}
      <SystemInstructionModal
        isOpen={isInstructionModalOpen}
        onClose={() => setIsInstructionModalOpen(false)}
        isDarkMode={isDarkMode}
        onSelect={handleSelectInstruction}
        currentInstructionId={currentInstruction?.id}
      />
    </div>
  );
}

export function ToolToggle({
  icon,
  label,
  checked,
  disabled = false,
  onCheckedChange,
}: {
  icon: React.ReactNode;
  label: string;
  checked: boolean;
  disabled?: boolean;
  onCheckedChange: (checked: boolean) => void;
}) {
  return (
    <div
      className={`flex items-center justify-between group ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
      onClick={() => !disabled && onCheckedChange(!checked)}
    >
      <div className="flex items-center gap-3">
        <div className={`transition-colors ${checked ? 'text-[var(--text-primary)]' : 'text-[var(--text-secondary)] group-hover:text-[var(--text-primary)]'}`}>{icon}</div>
        <span className={`text-sm transition-colors ${checked ? 'text-[var(--text-primary)]' : 'text-[var(--text-secondary)] group-hover:text-[var(--text-primary)]'}`}>{label}</span>
      </div>
      <Switch
        checked={checked}
        disabled={disabled}
        onCheckedChange={onCheckedChange}
        className="data-[state=checked]:bg-blue-600"
      />
    </div>
  );
}
