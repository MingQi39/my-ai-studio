import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, Eye, FileDown, Loader2, Sparkles, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { StructuredPlanDialog } from '@/features/travel/components/StructuredPlanDialog';
import { fetchFormalPlanStatus, generateStructuredPlan } from '@/features/travel/services/api/plan';
import { useTravelRuntime } from '@/features/travel/TravelRuntimeContext';
import type { FormalPlanCache, Message } from '@/features/travel/stores/useChatStore';
import { useChatStore } from '@/features/travel/stores/useChatStore';
import type { TravelPlanStatusResponse } from '@/features/travel/types/itinerary';
import {
  downloadMarkdownFile,
  sanitizeFilename,
} from '@/features/travel/utils/exportPlan';
import { downloadFormalPlanPdf } from '@/features/travel/services/api/plan';
import {
  computePlanFingerprint,
  extractLatestPlanPair,
  extractToolEvidence,
  getPlanFingerprint,
  hasExportablePlanContent,
} from '@/features/travel/utils/planContext';

interface PlanExportToolbarProps {
  messages: Message[];
  disabled?: boolean;
  visible?: boolean;
  onClose?: () => void;
}

function statusToCache(sessionId: string, status: TravelPlanStatusResponse): FormalPlanCache | null {
  if (!status.exists || !status.plan || !status.markdown) {
    return null;
  }

  const fingerprint =
    status.fingerprint ||
    (status.plan.title ? `${sessionId}:${status.plan.title}` : sessionId);

  return {
    sessionId,
    fingerprint,
    isStale: Boolean(status.is_stale),
    result: {
      plan: status.plan,
      markdown: status.markdown,
      fingerprint: status.fingerprint,
      exists: true,
      is_stale: status.is_stale,
      generated_at: status.generated_at,
    },
  };
}

export function PlanExportToolbar({
  messages,
  disabled = false,
  visible = true,
  onClose,
}: PlanExportToolbarProps) {
  const { t } = useTranslation();
  const { modelConfigId } = useTravelRuntime();
  const currentSessionId = useChatStore((state) => state.currentSessionId);
  const formalPlanCache = useChatStore((state) => state.formalPlanCache);
  const setFormalPlanCache = useChatStore((state) => state.setFormalPlanCache);

  const [busyAction, setBusyAction] = useState<'formal' | 'sync' | 'pdf' | null>(null);
  const [formalPlanOpen, setFormalPlanOpen] = useState(false);
  const syncRequestRef = useRef(0);
  const generateRequestRef = useRef(0);

  const canGenerate = hasExportablePlanContent(messages);
  const planFingerprint = getPlanFingerprint(messages);

  const activeFormalPlan =
    formalPlanCache && currentSessionId && formalPlanCache.sessionId === currentSessionId
      ? formalPlanCache.result
      : null;

  const hasFormalPlan = activeFormalPlan !== null && !formalPlanCache?.isStale;
  const hasStaleFormalPlan = activeFormalPlan !== null && Boolean(formalPlanCache?.isStale);

  // 正式规划书存在 session.description，与当前消息是否可导出无关，进入会话即应从后端恢复
  useEffect(() => {
    if (!currentSessionId) {
      setFormalPlanCache(null);
      return;
    }

    const requestId = ++syncRequestRef.current;
    setBusyAction((prev) => (prev === 'formal' ? prev : 'sync'));

    fetchFormalPlanStatus(currentSessionId)
      .then((status) => {
        if (requestId !== syncRequestRef.current) return;
        if (requestId <= generateRequestRef.current) return;
        setFormalPlanCache(statusToCache(currentSessionId, status));
      })
      .catch((error) => {
        if (requestId !== syncRequestRef.current) return;
        console.error('Failed to sync formal plan status:', error);
      })
      .finally(() => {
        if (requestId === syncRequestRef.current) {
          setBusyAction((prev) => (prev === 'sync' ? null : prev));
        }
      });
  }, [currentSessionId, planFingerprint, setFormalPlanCache]);

  const handleGenerateFormalPlan = async () => {
    if (!modelConfigId) {
      toast.error(t('travel.export.modelRequired'));
      return;
    }

    if (!currentSessionId) {
      toast.error(t('travel.export.sessionRequired'));
      return;
    }

    const pair = extractLatestPlanPair(messages);
    if (!pair) {
      toast.error(t('travel.export.noContent'));
      return;
    }

    const requestId = ++generateRequestRef.current;
    setBusyAction('formal');
    try {
      const result = await generateStructuredPlan({
        model_config_id: modelConfigId,
        session_id: currentSessionId,
        user_request: pair.userRequest,
        assistant_plan: pair.assistantPlan,
        tool_evidence: extractToolEvidence(messages),
        data_verified: pair.dataVerified,
      });

      if (requestId !== generateRequestRef.current) return;

      const fingerprint = result.fingerprint || computePlanFingerprint(pair.userRequest, pair.assistantPlan);
      setFormalPlanCache({
        sessionId: currentSessionId,
        fingerprint,
        isStale: false,
        result: {
          ...result,
          fingerprint,
          is_stale: false,
          exists: true,
        },
      });
      setFormalPlanOpen(true);
      toast.success(t('travel.export.formalPlanReady'));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('travel.export.formalPlanFailed'));
    } finally {
      if (requestId === generateRequestRef.current) {
        setBusyAction(null);
      }
    }
  };

  const handleOpenFormalPlan = () => {
    if (!activeFormalPlan) return;
    setFormalPlanOpen(true);
  };

  const handleExportFormalMarkdown = () => {
    const plan = activeFormalPlan?.plan;
    if (!activeFormalPlan?.markdown || !plan || formalPlanCache?.isStale) {
      toast.error(t('travel.export.formalPlanRequired'));
      return;
    }
    downloadMarkdownFile(
      activeFormalPlan.markdown,
      `${sanitizeFilename(plan.title)}-formal.md`,
    );
    toast.success(t('travel.export.exportMarkdownSuccess'));
  };

  const handleExportFormalPdf = async () => {
    const plan = activeFormalPlan?.plan;
    if (!plan || !currentSessionId || formalPlanCache?.isStale) {
      toast.error(t('travel.export.formalPlanRequired'));
      return;
    }
    setBusyAction('pdf');
    try {
      await downloadFormalPlanPdf(
        currentSessionId,
        plan.title || t('travel.export.documentTitle'),
      );
      toast.success(t('travel.export.exportPdfSuccess'));
    } catch (error) {
      const message = error instanceof Error ? error.message : t('travel.export.exportFailed');
      toast.error(message);
    } finally {
      setBusyAction(null);
    }
  };

  const isBusy = disabled || busyAction !== null;

  return (
    <>
      {visible && (
        <div className="sticky top-0 z-10 mb-4 space-y-3">
          {hasStaleFormalPlan && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 dark:border-amber-900/50 dark:bg-amber-950/30">
              <div className="flex min-w-0 items-start gap-2">
                <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-600" />
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-amber-900 dark:text-amber-100">
                    {t('travel.export.formalPlanStaleBanner')}
                  </p>
                  <p className="text-xs text-amber-700 dark:text-amber-300">
                    {t('travel.export.formalPlanStaleHint')}
                  </p>
                </div>
              </div>
            </div>
          )}

          <div className="rounded-xl border border-slate-200 bg-white/95 px-3 py-2.5 shadow-sm backdrop-blur-sm dark:border-slate-800 dark:bg-[#0F172A]/95">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
                  {t('travel.export.toolbarLabel')}
                </span>
                {!canGenerate && (
                  <p className="mt-0.5 text-[11px] text-slate-400">{t('travel.export.waitForPlan')}</p>
                )}
                {canGenerate && !hasFormalPlan && !hasStaleFormalPlan && (
                  <p className="mt-0.5 text-[11px] text-slate-400">{t('travel.export.generateFirstHint')}</p>
                )}
              </div>

              <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
                <Button
                  type="button"
                  variant="default"
                  size="sm"
                  disabled={isBusy || !canGenerate || !currentSessionId}
                  onClick={handleGenerateFormalPlan}
                  className="h-8 gap-1.5 text-xs"
                >
                  {busyAction === 'formal' ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Sparkles size={14} />
                  )}
                  {busyAction === 'formal'
                    ? t('travel.export.generatingFormal')
                    : hasFormalPlan
                      ? t('travel.export.regenerateFormal')
                      : t('travel.export.generateFormal')}
                </Button>

                {hasFormalPlan && (
                  <>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={isBusy}
                      onClick={handleOpenFormalPlan}
                      className="h-8 gap-1.5 text-xs"
                    >
                      <Eye size={14} />
                      {t('travel.export.viewFormalPlan')}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={isBusy}
                      onClick={handleExportFormalMarkdown}
                      className="h-8 gap-1.5 text-xs"
                    >
                      <FileDown size={14} />
                      {t('travel.export.exportMarkdown')}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={isBusy}
                      onClick={handleExportFormalPdf}
                      className="h-8 gap-1.5 text-xs"
                    >
                      {busyAction === 'pdf' ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <FileDown size={14} />
                      )}
                      {busyAction === 'pdf'
                        ? t('travel.export.exportingPdf')
                        : t('travel.export.exportPdf')}
                    </Button>
                  </>
                )}
                {onClose && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={onClose}
                    className="h-8 w-8 shrink-0 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                    aria-label={t('travel.export.toolbarClose')}
                  >
                    <X size={16} />
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      <StructuredPlanDialog
        open={formalPlanOpen}
        onOpenChange={setFormalPlanOpen}
        result={activeFormalPlan}
      />
    </>
  );
}
