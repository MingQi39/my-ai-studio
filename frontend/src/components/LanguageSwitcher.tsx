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
  /** Align dropdown to the start or end edge of the trigger. */
  menuAlign?: 'start' | 'end';
  /** Auth page uses explicit colors instead of app CSS variables. */
  tone?: 'app' | 'auth';
  isDarkMode?: boolean;
  className?: string;
}

export function LanguageSwitcher({
  dropUp = false,
  compact = false,
  menuAlign = 'start',
  tone = 'app',
  isDarkMode = false,
  className,
}: LanguageSwitcherProps) {
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

  const isAuthTone = tone === 'auth';
  const triggerClass = isAuthTone
    ? cn(
        'flex items-center gap-3 rounded-lg transition-colors group',
        compact ? 'px-2.5 py-2' : 'px-3 py-2',
        isDarkMode
          ? 'text-slate-300 hover:bg-slate-800 hover:text-white'
          : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
      )
    : cn(
        'flex items-center gap-3 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors group w-full',
        compact ? 'px-2 py-1.5' : 'px-3 py-2',
      );

  const menuClass = isAuthTone
    ? cn(
        'absolute z-[110] min-w-[200px] rounded-lg border shadow-lg overflow-hidden p-1',
        isDarkMode ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200',
        menuAlign === 'end' ? 'right-0' : 'left-0',
        dropUp ? 'bottom-full mb-2' : 'top-full mt-2',
      )
    : cn(
        'absolute z-50 min-w-[180px] rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] shadow-lg overflow-hidden p-1',
        menuAlign === 'end' ? 'right-0' : 'left-0 right-0',
        dropUp ? 'bottom-full mb-2' : 'top-full mt-2',
      );

  return (
    <div ref={wrapRef} className={cn('relative', className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        title={t('language.switcherTitle')}
        aria-expanded={open}
        aria-haspopup="listbox"
        className={triggerClass}
      >
        <Globe
          size={20}
          className={cn(
            'flex-shrink-0 transition-colors',
            isAuthTone
              ? isDarkMode
                ? 'text-slate-300 group-hover:text-white'
                : 'text-slate-600 group-hover:text-slate-900'
              : 'group-hover:text-[var(--text-primary)]',
          )}
        />
        {!compact && (
          <span
            className={cn(
              'text-sm font-medium transition-colors flex-1 text-left',
              isAuthTone
                ? isDarkMode
                  ? 'text-slate-300 group-hover:text-white'
                  : 'text-slate-700 group-hover:text-slate-900'
                : 'group-hover:text-[var(--text-primary)]',
            )}
          >
            {current.label}
          </span>
        )}
      </button>

      {open && (
        <div className={menuClass} role="listbox">
          <div
            className={cn(
              'text-[10px] font-semibold px-3 py-1.5 uppercase tracking-wider',
              isAuthTone
                ? isDarkMode
                  ? 'text-slate-400'
                  : 'text-slate-500'
                : 'text-[var(--text-secondary)]',
            )}
          >
            {t('language.switcherTitle')}
          </div>
          {SUPPORTED_LANGS.map((lang) => {
            const active = lang.code === current.code;
            return (
              <button
                key={lang.code}
                type="button"
                role="option"
                aria-selected={active}
                onClick={() => handlePick(lang.code)}
                className={cn(
                  'w-full flex items-center justify-between gap-2 px-3 py-2 rounded-md text-sm text-left transition-colors',
                  active
                    ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400'
                    : isAuthTone
                      ? isDarkMode
                        ? 'text-slate-200 hover:bg-slate-800'
                        : 'text-slate-700 hover:bg-slate-100'
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
