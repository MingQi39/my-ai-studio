import { Loader2 } from 'lucide-react';
import { BrandLogo } from '@/components/BrandLogo';
import { cn } from '@/components/ui/utils';

export type ChatQuickPrompt = {
  id: string;
  title: string;
  description?: string;
  onSelect: () => void;
};

type ChatEmptyStateProps = {
  loading?: boolean;
  loadingMessage?: string;
  logoAlt: string;
  title: string;
  subtitle?: string;
  quickPrompts?: ChatQuickPrompt[];
  variant?: 'travel' | 'studio';
  className?: string;
};

export function ChatEmptyState({
  loading = false,
  loadingMessage = '正在加载…',
  logoAlt,
  title,
  subtitle,
  quickPrompts,
  variant = 'travel',
  className,
}: ChatEmptyStateProps) {
  if (loading) {
    return (
      <div
        className={cn(
          'flex-1 flex flex-col items-center justify-center w-full px-6 pt-20 pb-10',
          className,
        )}
      >
        <Loader2 size={32} className="animate-spin text-[#3B82F6] mb-4" />
        <p className="text-slate-500 dark:text-slate-400">{loadingMessage}</p>
      </div>
    );
  }

  const isTravel = variant === 'travel';

  return (
    <div
      className={cn(
        'flex-1 flex flex-col items-center justify-center w-full px-6 animate-in fade-in duration-500',
        isTravel ? 'max-w-3xl pt-20 pb-10' : 'pt-[20vh]',
        className,
      )}
    >
      <BrandLogo size="lg" className={cn('opacity-90', isTravel ? 'mb-4' : 'mx-auto mb-4')} alt={logoAlt} />

      {isTravel ? (
        <>
          <h1 className="text-3xl font-bold mb-2 tracking-tight text-slate-800 dark:text-slate-100">{title}</h1>
          {subtitle && <p className="text-slate-500 dark:text-slate-400 mb-10">{subtitle}</p>}
        </>
      ) : (
        <div className="text-center">
          <p className="text-lg text-[var(--text-secondary)]">{title}</p>
          {subtitle && <p className="text-sm text-[var(--text-placeholder)] mt-2">{subtitle}</p>}
        </div>
      )}

      {quickPrompts && quickPrompts.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 w-full mb-8">
          {quickPrompts.map((prompt) => (
            <button
              key={prompt.id}
              type="button"
              onClick={prompt.onSelect}
              className="flex flex-col items-start p-5 bg-white dark:bg-[#151E2E] border border-slate-200 dark:border-slate-800 hover:border-[#3B82F6] dark:hover:border-[#3B82F6] rounded-2xl transition-all shadow-sm group hover:shadow-md"
            >
              <span className="text-[15px] font-bold text-slate-800 dark:text-slate-200 group-hover:text-[#3B82F6] transition-colors mb-2">
                ✨ {prompt.title}
              </span>
              {prompt.description && (
                <span className="text-xs text-slate-500 dark:text-slate-400 text-left">{prompt.description}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
