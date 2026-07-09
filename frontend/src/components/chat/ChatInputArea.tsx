import { useRef } from 'react';
import { Send, StopCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/components/ui/utils';

export type ChatInputAreaProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  canSubmit?: boolean;
  isGenerating?: boolean;
  onStop?: () => void;
  placeholder?: string;
  header?: React.ReactNode;
  prefix?: React.ReactNode;
  footer?: React.ReactNode;
  hint?: React.ReactNode;
  layout?: 'travel' | 'studio';
  containerClassName?: string;
  innerClassName?: string;
  textareaClassName?: string;
  textareaRef?: React.RefObject<HTMLTextAreaElement | null>;
  sendButton?: React.ReactNode;
  textareaRows?: number;
  textareaMaxHeight?: string;
};

export function ChatInputArea({
  value,
  onChange,
  onSubmit,
  disabled = false,
  canSubmit,
  isGenerating = false,
  onStop,
  placeholder,
  header,
  prefix,
  footer,
  hint,
  layout = 'travel',
  containerClassName,
  innerClassName,
  textareaClassName,
  textareaRef,
  sendButton,
  textareaRows = 1,
  textareaMaxHeight,
}: ChatInputAreaProps) {
  const { t } = useTranslation();
  const submitEnabled = canSubmit ?? !!value.trim();
  const showStopButton = isGenerating && !!onStop;
  const isComposingRef = useRef(false);
  const justEndedCompositionRef = useRef(false);

  const handleCompositionStart = () => {
    isComposingRef.current = true;
    justEndedCompositionRef.current = false;
  };

  const handleCompositionEnd = () => {
    isComposingRef.current = false;
    // Some browsers fire Enter keydown right after compositionend with isComposing=false.
    justEndedCompositionRef.current = true;
    window.setTimeout(() => {
      justEndedCompositionRef.current = false;
    }, 0);
  };

  const isImeComposing = (event: React.KeyboardEvent<HTMLTextAreaElement>) =>
    event.nativeEvent.isComposing ||
    isComposingRef.current ||
    justEndedCompositionRef.current ||
    event.keyCode === 229;

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      if (isImeComposing(event)) {
        return;
      }
      event.preventDefault();
      if (!disabled && submitEnabled) {
        onSubmit();
      }
    }
  };

  const textarea = (
    <textarea
      ref={textareaRef}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      onCompositionStart={handleCompositionStart}
      onCompositionEnd={handleCompositionEnd}
      onKeyDown={handleKeyDown}
      placeholder={placeholder}
      disabled={disabled}
      rows={textareaRows}
      style={textareaMaxHeight ? { maxHeight: textareaMaxHeight } : undefined}
      className={cn(
        layout === 'travel'
          ? 'w-full max-h-48 min-h-[56px] py-4 pl-4 pr-16 bg-transparent border-none outline-none text-base placeholder-slate-400 resize-none overflow-y-auto text-slate-800 dark:text-slate-200'
          : 'w-full bg-transparent border-none outline-none text-[var(--text-primary)] placeholder:text-[var(--text-placeholder)] resize-none min-h-[40px] px-4 py-2 text-base custom-scrollbar',
        textareaClassName,
      )}
    />
  );

  if (layout === 'studio') {
    return (
      <div className={containerClassName}>
        <div className={innerClassName}>
          {prefix}
          {textarea}
          {footer}
        </div>
      </div>
    );
  }

  return (
    <>
      <div className={containerClassName}>
        <div className={innerClassName}>
          {header}
          <div className="relative flex items-end">
            {textarea}
            {sendButton ?? (
              <button
                type="button"
                onClick={showStopButton ? onStop : onSubmit}
                disabled={showStopButton ? false : !submitEnabled || disabled}
                aria-label={
                  showStopButton ? t('workspace.stopGenerate') : t('workspace.send', { defaultValue: 'Send' })
                }
                className={cn(
                  'absolute right-3 bottom-3 p-2 rounded-xl transition-all flex items-center justify-center',
                  showStopButton
                    ? 'bg-red-500 hover:bg-red-600 text-white shadow-md'
                    : submitEnabled && !disabled
                      ? 'bg-[#3B82F6] hover:bg-[#2563EB] text-white shadow-md'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-400 cursor-not-allowed',
                )}
              >
                {showStopButton ? (
                  <StopCircle size={18} className="fill-current" />
                ) : (
                  <Send size={18} />
                )}
              </button>
            )}
          </div>
        </div>
      </div>
      {hint}
    </>
  );
}
