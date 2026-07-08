import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Bot,
  Cloud,
  ExternalLink,
  Loader2,
  Sparkles,
  Terminal,
  Trash2,
  Zap,
} from 'lucide-react';
import { toast } from 'sonner';
import { BrandLogo } from '@/components/BrandLogo';
import { cn } from '@/components/ui/utils';
import { listModelConfigs, type ModelConfigResponse, type SessionResponse } from '@/services/api';

type LaunchpadBadge = { textKey: string; color: 'blue' | 'green' | 'purple' | 'orange' | 'grey' };

type LaunchpadModelDef = {
  id: string;
  providerId: string;
  titleKey: string;
  descKey: string;
  icon: React.ReactNode;
  iconBg: string;
  badgeKeys: LaunchpadBadge[];
  categories: string[];
};

const LAUNCHPAD_MODELS: LaunchpadModelDef[] = [
  {
    id: 'deepseek',
    providerId: 'deepseek',
    titleKey: 'launchpad.models.deepseek.title',
    descKey: 'launchpad.models.deepseek.desc',
    icon: <Bot size={18} className="text-blue-500" />,
    iconBg: 'bg-blue-500/10',
    badgeKeys: [
      { textKey: 'launchpad.badges.new', color: 'green' },
      { textKey: 'launchpad.badges.opensource', color: 'grey' },
    ],
    categories: ['all', 'text'],
  },
  {
    id: 'openai',
    providerId: 'openai',
    titleKey: 'launchpad.models.openai.title',
    descKey: 'launchpad.models.openai.desc',
    icon: <Zap size={18} className="text-emerald-500" />,
    iconBg: 'bg-emerald-500/10',
    badgeKeys: [{ textKey: 'launchpad.badges.paid', color: 'blue' }],
    categories: ['all', 'text'],
  },
  {
    id: 'gemini',
    providerId: 'gemini',
    titleKey: 'launchpad.models.gemini.title',
    descKey: 'launchpad.models.gemini.desc',
    icon: <Sparkles size={18} className="text-indigo-500" />,
    iconBg: 'bg-indigo-500/10',
    badgeKeys: [{ textKey: 'launchpad.badges.multimodal', color: 'purple' }],
    categories: ['all', 'multimodal'],
  },
  {
    id: 'qwen',
    providerId: 'qwen',
    titleKey: 'launchpad.models.qwen.title',
    descKey: 'launchpad.models.qwen.desc',
    icon: <Cloud size={18} className="text-purple-500" />,
    iconBg: 'bg-purple-500/10',
    badgeKeys: [{ textKey: 'launchpad.badges.localCapable', color: 'orange' }],
    categories: ['all', 'text', 'local'],
  },
  {
    id: 'openrouter',
    providerId: 'openrouter',
    titleKey: 'launchpad.models.openrouter.title',
    descKey: 'launchpad.models.openrouter.desc',
    icon: <ExternalLink size={18} className="text-green-500" />,
    iconBg: 'bg-green-500/10',
    badgeKeys: [{ textKey: 'launchpad.badges.aggregator', color: 'blue' }],
    categories: ['all', 'text'],
  },
  {
    id: 'ollama',
    providerId: 'ollama',
    titleKey: 'launchpad.models.ollama.title',
    descKey: 'launchpad.models.ollama.desc',
    icon: <Terminal size={18} className="text-orange-500" />,
    iconBg: 'bg-orange-500/10',
    badgeKeys: [{ textKey: 'launchpad.badges.local', color: 'orange' }],
    categories: ['all', 'local'],
  },
];

function configMatchesProvider(config: ModelConfigResponse, providerId: string): boolean {
  if (config.adapter_type === 'official' && config.provider === providerId) return true;
  return config.adapter_type === providerId;
}

export type StudioLaunchpadProps = {
  sessions: SessionResponse[];
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string, e: React.MouseEvent) => void;
  isLoadingSessions: boolean;
  onOpenConnectionModal: (selectedProviderId?: string) => void;
  onSelectProviderModel: (providerId: string, displayName: string) => void;
};

export function StudioLaunchpad({
  sessions,
  onSelectSession,
  onDeleteSession,
  isLoadingSessions,
  onOpenConnectionModal,
  onSelectProviderModel,
}: StudioLaunchpadProps) {
  const { t, i18n } = useTranslation();
  const [activeTab, setActiveTab] = useState('all');
  const [modelConfigs, setModelConfigs] = useState<ModelConfigResponse[]>([]);

  useEffect(() => {
    listModelConfigs()
      .then(setModelConfigs)
      .catch((err) => console.error('Failed to load model configs:', err));
  }, []);

  const isProviderConfigured = (providerId: string) =>
    modelConfigs.some((config) => configMatchesProvider(config, providerId));

  const filteredModels = LAUNCHPAD_MODELS.filter((model) => model.categories.includes(activeTab));

  const handleModelClick = (providerId: string, displayName: string) => {
    if (!isProviderConfigured(providerId)) {
      toast.info(t('launchpad.configureFirst', { name: displayName }));
      onOpenConnectionModal(providerId);
    } else {
      onSelectProviderModel(providerId, displayName);
    }
  };

  return (
    <div className="w-full max-w-[850px] mx-auto flex flex-col items-center pt-[4vh] sm:pt-[5vh] px-4 sm:px-6 pb-12">
      <div className="text-center flex flex-col items-center mb-6 sm:mb-8 gap-3 sm:gap-4">
        <div className="rounded-2xl shadow-sm overflow-hidden p-2">
          <BrandLogo size="xl" alt={t('common.appName')} />
        </div>
        <div className="flex flex-col gap-2">
          <h1 className="text-[20px] sm:text-[24px] font-semibold text-[var(--text-primary)] tracking-tight">
            {t('launchpad.title')}
          </h1>
          <p className="text-[var(--text-secondary)] text-[13px] sm:text-[14px] leading-relaxed max-w-[500px] px-1">
            {t('launchpad.subtitle')}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 mb-8 flex-wrap justify-center">
        <FilterTab label={t('launchpad.tabAll')} id="all" activeTab={activeTab} onClick={setActiveTab} />
        <FilterTab label={t('launchpad.tabText')} id="text" activeTab={activeTab} onClick={setActiveTab} />
        <FilterTab label={t('launchpad.tabMultimodal')} id="multimodal" activeTab={activeTab} onClick={setActiveTab} />
        <FilterTab label={t('launchpad.tabLocal')} id="local" activeTab={activeTab} onClick={setActiveTab} />
      </div>

      <div className="w-full flex flex-col border-t border-[var(--border-color)]">
        {filteredModels.length === 0 ? (
          <div className="py-8 text-center text-[var(--text-secondary)]">
            <p className="text-sm">{t('launchpad.noMatch')}</p>
          </div>
        ) : (
          filteredModels.map((model) => (
            <ModelRow
              key={model.id}
              title={t(model.titleKey)}
              desc={t(model.descKey)}
              icon={model.icon}
              iconBg={model.iconBg}
              badges={model.badgeKeys.map((badge) => ({ text: t(badge.textKey), color: badge.color }))}
              onClick={() => handleModelClick(model.providerId, t(model.titleKey))}
              isConfigured={isProviderConfigured(model.providerId)}
            />
          ))
        )}
      </div>

      {sessions.length > 0 && (
        <div className="w-full mt-8">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)] mb-4">{t('launchpad.recentSessions')}</h2>
          <div className="w-full flex flex-col border border-[var(--border-color)] rounded-lg overflow-hidden">
            {isLoadingSessions ? (
              <div className="p-4 text-center text-[var(--text-secondary)]">
                <Loader2 size={20} className="animate-spin mx-auto" />
              </div>
            ) : (
              sessions
                .filter((session) => session.message_count > 0)
                .slice(0, 3)
                .map((session) => (
                  <div
                    key={session.id}
                    onClick={() => onSelectSession(session.id)}
                    className="flex items-center justify-between px-4 py-3 hover:bg-[var(--bg-hover)] cursor-pointer transition-colors border-b border-[var(--border-color)] last:border-b-0 group"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-[var(--text-primary)] truncate">{session.title}</p>
                      <p className="text-xs text-[var(--text-secondary)]">
                        {t('sidebar.messageCount', { count: session.message_count })} ·{' '}
                        {new Date(session.updated_at).toLocaleDateString(i18n.language)}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={(event) => onDeleteSession(session.id, event)}
                      className="opacity-100 md:opacity-0 md:group-hover:opacity-100 p-1.5 hover:bg-red-500/10 rounded-md text-[var(--text-secondary)] hover:text-red-500 transition-all"
                      aria-label={t('sidebar.deleteSessionTitle')}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function FilterTab({
  label,
  id,
  activeTab,
  onClick,
}: {
  label: string;
  id: string;
  activeTab: string;
  onClick: (id: string) => void;
}) {
  const isActive = activeTab === id;
  return (
    <button
      type="button"
      onClick={() => onClick(id)}
      className={cn(
        'px-4 py-1.5 rounded-full text-xs font-medium transition-all duration-200',
        isActive
          ? 'bg-[var(--text-primary)] text-[var(--bg-main)]'
          : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]',
      )}
    >
      {label}
    </button>
  );
}

function ModelRow({
  title,
  desc,
  icon,
  iconBg,
  badges,
  onClick,
  isConfigured,
}: {
  title: string;
  desc: string;
  icon: React.ReactNode;
  iconBg: string;
  badges: { text: string; color: 'blue' | 'green' | 'purple' | 'orange' | 'grey' }[];
  onClick: () => void;
  isConfigured?: boolean;
}) {
  const { t } = useTranslation();

  const getBadgeColor = (color: string) => {
    switch (color) {
      case 'green':
        return 'text-green-500 bg-green-500/10';
      case 'blue':
        return 'text-blue-500 bg-blue-500/10';
      case 'purple':
        return 'text-purple-500 bg-purple-500/10';
      case 'orange':
        return 'text-orange-500 bg-orange-500/10';
      default:
        return 'text-[var(--text-secondary)] bg-[var(--bg-hover)]';
    }
  };

  return (
    <div
      onClick={onClick}
      className="group flex items-center min-h-[72px] px-2 sm:px-4 py-3 border-b border-[var(--border-color)] last:border-0 hover:bg-[var(--bg-hover)] transition-colors duration-200 cursor-pointer rounded-lg"
    >
      <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center shrink-0', iconBg)}>{icon}</div>
      <div className="flex-1 min-w-0 ml-4 flex flex-col justify-center gap-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-bold text-[var(--text-primary)]">{title}</span>
          <div className="flex items-center gap-1.5">
            {badges.map((badge, index) => (
              <span
                key={index}
                className={cn('text-[10px] px-1.5 py-0.5 rounded-sm font-medium', getBadgeColor(badge.color))}
              >
                {badge.text}
              </span>
            ))}
            {isConfigured !== undefined && (
              <span
                className={cn(
                  'text-[10px] px-1.5 py-0.5 rounded-sm font-medium',
                  isConfigured ? 'text-green-600 bg-green-500/10' : 'text-amber-600 bg-amber-500/10',
                )}
              >
                {isConfigured ? t('launchpad.statusConfigured') : t('launchpad.statusPending')}
              </span>
            )}
          </div>
        </div>
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{desc}</p>
      </div>
    </div>
  );
}
