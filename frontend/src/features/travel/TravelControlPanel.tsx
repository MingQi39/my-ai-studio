import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Brain, CheckCircle2, AlertTriangle, Plug, Save, Loader2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import {
  fetchTravelSettings,
  updateTravelSettings,
  type TravelSettings,
} from '@/features/travel/services/api/settings';

interface TravelControlPanelProps {
  selectedModel: string;
  onOpenModelSettings: () => void;
  isOpen: boolean;
  onClose?: () => void;
}

export function TravelControlPanel({
  selectedModel,
  onOpenModelSettings,
  isOpen,
  onClose,
}: TravelControlPanelProps) {
  const { t } = useTranslation();
  const [settings, setSettings] = useState<TravelSettings | null>(null);
  const [maxRounds, setMaxRounds] = useState(3);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    fetchTravelSettings()
      .then((data) => {
        setSettings(data);
        setMaxRounds(data.max_rounds);
      })
      .catch(() => toast.error(t('travel.panel.loadFailed')))
      .finally(() => setLoading(false));
  }, [isOpen, t]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateTravelSettings({ max_rounds: maxRounds });
      toast.success(t('travel.panel.saved'));
    } catch {
      toast.error(t('travel.panel.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="w-full md:w-[300px] h-full flex flex-col border-l border-[var(--border-color)]"
      style={{ backgroundColor: 'var(--bg-panel)' }}
    >
      <div className="p-4 border-b border-[var(--border-color)] flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">{t('travel.panel.title')}</h2>
          <p className="text-xs text-[var(--text-secondary)] mt-1">{t('travel.panel.subtitle')}</p>
        </div>
        {onClose && (
          <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0 md:hidden" onClick={onClose}>
            <X size={16} />
          </Button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-5 custom-scrollbar">
        <section className="rounded-xl border border-[var(--border-color)] p-4 space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium text-[var(--text-primary)]">
            <Brain size={16} className="text-blue-500" />
            {t('travel.panel.model')}
          </div>
          <p className="text-xs text-[var(--text-secondary)]">{t('travel.panel.modelHint')}</p>
          <div className="text-sm font-mono px-3 py-2 rounded-lg bg-[var(--bg-hover)] truncate">
            {selectedModel || t('travel.panel.noModel')}
          </div>
          <Button variant="outline" size="sm" className="w-full" onClick={onOpenModelSettings}>
            <Plug size={14} className="mr-2" />
            {t('travel.panel.openModelSettings')}
          </Button>
        </section>

        <section className="rounded-xl border border-[var(--border-color)] p-4 space-y-3">
          <label className="text-sm font-medium text-[var(--text-primary)]">
            {t('travel.panel.maxRounds')}
          </label>
          <input
            type="number"
            min={1}
            max={10}
            value={maxRounds}
            onChange={(e) => setMaxRounds(Number(e.target.value))}
            disabled={loading}
            className="w-full px-3 py-2 text-sm rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)]"
          />
          <Button size="sm" className="w-full" onClick={handleSave} disabled={loading || saving}>
            {saving ? <Loader2 size={14} className="mr-2 animate-spin" /> : <Save size={14} className="mr-2" />}
            {t('travel.panel.saveAgentParams')}
          </Button>
        </section>

        <section className="rounded-xl border border-[var(--border-color)] p-4 space-y-2">
          <p className="text-sm font-medium text-[var(--text-primary)]">{t('travel.panel.tools')}</p>
          {loading ? (
            <p className="text-xs text-[var(--text-secondary)]">{t('common.loading')}</p>
          ) : (
            <>
              <ToolStatus ok={!!settings?.amap_api_key} label={t('travel.panel.amap')} />
              <ToolStatus ok={!!settings?.juhe_train_api_key} label={t('travel.panel.juheTrain')} />
              <ToolStatus ok={!!settings?.juhe_flight_api_key} label={t('travel.panel.juheFlight')} />
              <ToolStatus ok={!!settings?.tavily_api_key} label={t('travel.panel.tavily')} />
            </>
          )}
        </section>
      </div>
    </div>
  );
}

function ToolStatus({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
      {ok ? (
        <CheckCircle2 size={14} className="text-emerald-500" />
      ) : (
        <AlertTriangle size={14} className="text-amber-500" />
      )}
      <span>
        {label}: {ok ? 'OK' : '—'}
      </span>
    </div>
  );
}
