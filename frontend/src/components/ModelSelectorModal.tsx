import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { X, ExternalLink, Check, ChevronDown, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { toast } from 'sonner';
import { cn } from '@/components/ui/utils';

interface ModelSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (modelName: string) => void;
  isDarkMode: boolean;
}

export function ModelSelectorModal({ isOpen, onClose, onSelect, isDarkMode }: ModelSelectorModalProps) {
  const { t } = useTranslation();
  const [selectedProject, setSelectedProject] = useState("Default Gemini Project");
  const [saveKey, setSaveKey] = useState(false);
  const [selectedModel, setSelectedModel] = useState("gemini-pro");

  if (!isOpen) return null;

  const handleSave = () => {
    toast.success(t('modelSelector.switched'));
    onSelect("Gemini 3 Pro Preview");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-200 p-0 sm:p-4">
      <div 
        className="w-full sm:w-[520px] sm:max-w-[calc(100vw-2rem)] max-h-[92dvh] rounded-t-2xl sm:rounded-[16px] shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-200 transition-colors"
        style={{ 
            backgroundColor: 'var(--bg-card)',
            color: 'var(--text-primary)',
            boxShadow: isDarkMode ? '0 25px 50px -12px rgba(0, 0, 0, 0.7)' : '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
        }}
      >
        
        {/* 1. Header */}
        <div className="flex items-center justify-between px-4 sm:px-6 pt-5 sm:pt-6 pb-2">
          <h2 className="text-[18px] font-bold tracking-tight">{t('modelSelector.title')}</h2>
          <button 
            onClick={onClose}
            className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors rounded-full p-1 hover:bg-[var(--bg-hover)]"
          >
            <X size={20} />
          </button>
        </div>

        {/* 2. Content */}
        <div className="p-4 sm:p-6 pt-2 flex flex-col gap-6 overflow-y-auto">
            
            {/* Project Selection */}
            <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-[var(--text-secondary)]">{t('modelSelector.selectProject')}</label>
                <div className="relative group">
                    <select 
                        value={selectedProject}
                        onChange={(e) => setSelectedProject(e.target.value)}
                        className="w-full h-[48px] px-4 rounded-lg border appearance-none outline-none transition-all cursor-pointer bg-transparent text-[var(--text-primary)] border-[var(--border-color)] hover:border-[var(--text-secondary)] focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                    >
                        <option value="Default Gemini Project">{t('modelSelector.defaultProject')}</option>
                        <option value="Project B">Project Alpha</option>
                    </select>
                    <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 text-[var(--text-secondary)] pointer-events-none" size={16} />
                </div>
            </div>

            {/* Key Selection */}
            <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-[var(--text-secondary)]">{t('modelSelector.key')}</label>
                <div className="relative group">
                    <div className="w-full h-[48px] px-4 rounded-lg border flex items-center justify-between transition-all bg-transparent text-[var(--text-primary)] border-[var(--border-color)] group-hover:border-[var(--text-secondary)]">
                         <span className="font-mono text-sm tracking-wide">adk • • • • • • • • m9kg</span>
                         <ChevronDown className="text-[var(--text-secondary)]" size={16} />
                    </div>
                </div>
            </div>

            {/* Actions Row */}
            <div className="flex items-center justify-between pt-1">
                <a href="#" className="flex items-center gap-1.5 text-sm font-medium text-blue-500 hover:text-blue-600 transition-colors">
                    {t('modelSelector.manageKeys')}
                    <ExternalLink size={14} />
                </a>

                <div className="flex items-center gap-3">
                    <span className="text-sm text-[var(--text-primary)]">{t('modelSelector.savePaidKey')}</span>
                    <Switch checked={saveKey} onCheckedChange={setSaveKey} />
                </div>
            </div>

            {/* Recommended Model */}
            <div className="flex flex-col gap-3 pt-2">
                <label className="text-sm font-medium text-[var(--text-secondary)]">{t('modelSelector.recommended')}</label>
                
                <div 
                    onClick={() => setSelectedModel('gemini-pro')}
                    className={cn(
                        "relative flex items-center p-4 rounded-xl border-2 transition-all cursor-pointer overflow-hidden",
                        selectedModel === 'gemini-pro' 
                            ? "border-blue-200 bg-blue-50 dark:bg-blue-900/20 dark:border-blue-800" 
                            : "border-[var(--border-color)] hover:bg-[var(--bg-hover)]"
                    )}
                >
                    {/* Icon */}
                    <div className="w-10 h-10 rounded-lg bg-[#1867DC] flex items-center justify-center text-white shrink-0 mr-4 shadow-sm">
                        <Zap size={20} fill="currentColor" className="text-white" />
                    </div>

                    {/* Text */}
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                            <span className="font-semibold text-[var(--text-primary)]">Gemini 3 Pro Preview</span>
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300">New</span>
                        </div>
                        <p className="text-xs text-[var(--text-secondary)] truncate">
                            SOTA reasoning and multimodal understanding
                        </p>
                    </div>

                    {/* Checkmark */}
                    {selectedModel === 'gemini-pro' && (
                        <div className="text-blue-500 ml-3">
                            <Check size={20} />
                        </div>
                    )}
                </div>
            </div>

        </div>

        {/* 3. Footer */}
        <div className="px-4 sm:px-6 py-4 sm:py-6 pt-2 flex items-center justify-end gap-3">
             <Button 
                variant="ghost" 
                onClick={onClose}
                className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] font-medium"
             >
                {t('modelSelector.cancelLink')}
             </Button>
             <Button 
                onClick={handleSave}
                className={cn(
                    "font-medium px-6 shadow-lg transition-colors",
                    isDarkMode 
                        ? "bg-white text-black hover:bg-gray-200" 
                        : "bg-[#181B1F] text-white hover:bg-[#2C3036]"
                )}
             >
                {t('modelSelector.selectKey')}
             </Button>
        </div>

      </div>
    </div>
  );
}
