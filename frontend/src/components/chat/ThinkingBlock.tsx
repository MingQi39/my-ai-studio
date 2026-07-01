import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown, Sparkles } from 'lucide-react';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { cn } from '@/components/ui/utils';

type ThinkingBlockProps = {
  text: string;
  isStreaming?: boolean;
  isDarkMode?: boolean;
};

export function ThinkingBlock({ text, isStreaming, isDarkMode = false }: ThinkingBlockProps) {
  const [isOpen, setIsOpen] = useState(false);
  const { t } = useTranslation();

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className={cn(
        'w-full rounded-xl overflow-hidden border mb-2 transition-colors duration-200',
        isDarkMode ? 'bg-[#1E1F20] border-[#2E2F31]' : 'bg-gray-50 border-gray-200',
      )}
    >
      <CollapsibleTrigger asChild>
        <div
          className={cn(
            'w-full px-4 py-3 cursor-pointer transition-colors flex items-center justify-between group select-none',
            isDarkMode ? 'hover:bg-[#252628]' : 'hover:bg-gray-100',
          )}
        >
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-blue-400 fill-blue-400/20" />
            <span className={cn('text-sm font-semibold', isDarkMode ? 'text-gray-200' : 'text-gray-800')}>
              {t('workspace.deepThinking')}
              {isStreaming && <span className="animate-pulse ml-1">...</span>}
            </span>
            {!isOpen && <span className="text-xs text-gray-500 ml-2">{t('workspace.expandThinking')}</span>}
          </div>
          <div className={cn('text-gray-500 transition-transform duration-200', isOpen && 'rotate-180')}>
            <ChevronDown size={16} />
          </div>
        </div>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className={cn('px-4 pb-4 pt-1', isDarkMode ? 'bg-[#1E1F20]' : 'bg-gray-50')}>
          <div className="relative pl-4 border-l-2 border-blue-500/30 ml-1">
            <p
              className={cn(
                'text-sm leading-relaxed whitespace-pre-wrap font-sans',
                isDarkMode ? 'text-gray-400' : 'text-gray-600',
              )}
            >
              {text}
              {isStreaming && (
                <span className="inline-block w-1.5 h-4 ml-1 align-middle bg-blue-500 animate-pulse" />
              )}
            </p>
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
