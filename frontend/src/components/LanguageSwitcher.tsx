import { useState, useEffect, useRef } from 'react';
import { Globe, Check } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { SUPPORTED_LANGS, setLanguage, type SupportedLang } from '@/i18n';
import { cn } from '@/components/ui/utils';

interface LanguageSwitcherProps {
  /** When true, pin the dropdown above the trigger (use inside a sidebar footer). */
  dropUp?: boolean;
  /** Render as a compact icon-only trigger instead of the full row. */
  compact?: boolean;
  className?: string;
}

export function LanguageSwitcher({ dropUp = false, compact = false, className }: LanguageSwitcherProps) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  const current =
    SUPPORTED_LANGS.find((l) => l.code === i18n.language) ||
    SUPPORTED_LANGS.find((l) => i18n.language?.startsWith(l.code.split('-')[0])) ||
    SUPPORTED_LANGS[0];

  const handlePick = (code: SupportedLang) => {
    setLanguage(code);
    setOpen(false);
  };

  return (
    <div ref={wrapRef} className={cn('relative', className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        title={t('language.switcherTitle')}
        className={cn(
          'flex items-center gap-3 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors group w-full',
          compact ? 'px-2 py-1.5' : 'px-3 py-2',
        )}
      >
        <Globe size={20} className="group-hover:text-[var(--text-primary)] transition-colors flex-shrink-0" />
        {!compact && (
          <span className="text-sm font-medium group-hover:text-[var(--text-primary)] transition-colors flex-1 text-left">
            {current.label}
          </span>
        )}
      </button>

      {open && (
        <div
          className={cn(
            'absolute z-50 left-0 right-0 min-w-[180px] rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] shadow-lg overflow-hidden p-1',
            dropUp ? 'bottom-full mb-2' : 'top-full mt-2',
          )}
          style={{ backgroundColor: 'var(--bg-card)' }}
        >
          <div className="text-[10px] font-semibold text-[var(--text-secondary)] px-3 py-1.5 uppercase tracking-wider">
            {t('language.switcherTitle')}
          </div>
          {SUPPORTED_LANGS.map((lang) => {
            const active = lang.code === current.code;
            return (
              <button
                key={lang.code}
                onClick={() => handlePick(lang.code)}
                className={cn(
                  'w-full flex items-center justify-between gap-2 px-3 py-2 rounded-md text-sm text-left transition-colors',
                  active
                    ? 'bg-blue-500/10 text-blue-600 dark:text-[#A8C7FA]'
                    : 'text-[var(--text-primary)] hover:bg-[var(--bg-hover)]',
                )}
              >
                <span className="truncate">{lang.label}</span>
                {active && <Check size={14} className="flex-shrink-0" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
