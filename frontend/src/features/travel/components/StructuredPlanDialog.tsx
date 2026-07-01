import { Calendar, Copy, ExternalLink, FileDown, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import type { StructuredTravelPlan, TravelPlanGenerateResponse } from '@/features/travel/types/itinerary';
import {
  copyTextToClipboard,
  downloadMarkdownFile,
  sanitizeFilename,
} from '@/features/travel/utils/exportPlan';
import {
  buildIcsCalendar,
  collectPlanNavLinks,
  downloadIcsFile,
} from '@/features/travel/utils/formalPlanExport';
import { downloadFormalPlanPdf } from '@/features/travel/services/api/plan';
import { useChatStore } from '@/features/travel/stores/useChatStore';

interface StructuredPlanDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  result: TravelPlanGenerateResponse | null;
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-800 dark:bg-[#1E293B]/60">
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 break-words text-sm font-semibold text-slate-800 dark:text-slate-100">{value}</div>
    </div>
  );
}

function DaySection({
  day,
  destination,
}: {
  day: StructuredTravelPlan['daily_itinerary'][number];
  destination: string;
}) {
  return (
    <section className="rounded-xl border border-slate-200 p-4 dark:border-slate-800">
      <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">
        Day {day.day}{day.title ? ` · ${day.title}` : ''}
      </h3>
      <div className="mt-3 space-y-3">
        {day.activities.map((activity, index) => (
          <div key={`${day.day}-${index}`} className="border-l-2 border-[#3B82F6]/40 pl-3">
            <div className="break-words text-sm font-semibold text-slate-800 dark:text-slate-100">
              {activity.time ? `${activity.time} · ` : ''}{activity.title}
            </div>
            {activity.description && (
              <p className="mt-1 break-words text-sm text-slate-600 dark:text-slate-400">{activity.description}</p>
            )}
            {activity.location && (
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span className="break-words">
                  📍 {activity.location.name}
                  {activity.location.address ? `（${activity.location.address}）` : ''}
                </span>
                <a
                  href={`https://uri.amap.com/search?query=${encodeURIComponent(
                    [activity.location.name, activity.location.address, destination].filter(Boolean).join(' '),
                  )}&city=${encodeURIComponent(destination)}`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex shrink-0 items-center gap-1 text-[#3B82F6] hover:underline"
                >
                  <ExternalLink size={12} />
                  高德导航
                </a>
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

export function StructuredPlanDialog({ open, onOpenChange, result }: StructuredPlanDialogProps) {
  const { t } = useTranslation();
  const currentSessionId = useChatStore((state) => state.currentSessionId);
  const [copiedLinks, setCopiedLinks] = useState(false);
  const [exportingPdf, setExportingPdf] = useState(false);
  const plan = result?.plan;
  const navLinks = plan ? collectPlanNavLinks(plan) : [];

  if (!plan || !result) {
    return null;
  }

  const handleDownload = () => {
    downloadMarkdownFile(result.markdown, `${sanitizeFilename(plan.title)}-formal.md`);
    toast.success(t('travel.export.exportMarkdownSuccess'));
  };

  const handleExportPdf = async () => {
    if (!currentSessionId) {
      toast.error(t('travel.export.sessionRequired'));
      return;
    }
    setExportingPdf(true);
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
      setExportingPdf(false);
    }
  };

  const handleExportCalendar = () => {
    const ics = buildIcsCalendar(plan);
    downloadIcsFile(ics, `${sanitizeFilename(plan.title)}.ics`);
    toast.success(t('travel.export.exportCalendarSuccess'));
  };

  const handleCopyNavLinks = async () => {
    if (!navLinks.length) return;
    const text = navLinks
      .map((item) => `${item.name}${item.address ? `（${item.address}）` : ''}: ${item.url}`)
      .join('\n');
    try {
      await copyTextToClipboard(text);
      setCopiedLinks(true);
      toast.success(t('travel.export.navLinksCopied'));
      setTimeout(() => setCopiedLinks(false), 2000);
    } catch {
      toast.error(t('travel.export.copyFailed'));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[90vh] w-[calc(100%-2rem)] max-w-3xl flex-col gap-0 overflow-hidden p-0 sm:max-w-3xl">
        <DialogHeader className="space-y-4 border-b border-slate-200 px-6 py-5 pr-14 text-left dark:border-slate-800">
          <div className="min-w-0 space-y-2">
            <DialogTitle className="text-left text-xl font-bold leading-snug break-words">
              {plan.title}
            </DialogTitle>
            {plan.summary && (
              <p className="text-left text-sm leading-relaxed break-words text-slate-600 dark:text-slate-400">
                {plan.summary}
              </p>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" size="sm" onClick={handleExportCalendar} className="h-8 gap-1.5 text-xs">
              <Calendar size={14} />
              {t('travel.export.exportCalendar')}
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={handleDownload} className="h-8 gap-1.5 text-xs">
              <FileDown size={14} />
              {t('travel.export.exportMarkdown')}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={exportingPdf}
              onClick={handleExportPdf}
              className="h-8 gap-1.5 text-xs"
            >
              {exportingPdf ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <FileDown size={14} />
              )}
              {exportingPdf ? t('travel.export.exportingPdf') : t('travel.export.exportPdf')}
            </Button>
          </div>
        </DialogHeader>

        <div className="custom-scrollbar min-h-0 flex-1 space-y-5 overflow-y-auto px-6 py-5">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MetaItem label={t('travel.export.destination')} value={plan.destination} />
            {plan.duration_days != null && (
              <MetaItem label={t('travel.export.duration')} value={`${plan.duration_days} ${t('travel.export.days')}`} />
            )}
            {plan.travel_dates && (
              <MetaItem label={t('travel.export.dates')} value={plan.travel_dates} />
            )}
            {plan.budget_total != null && (
              <MetaItem
                label={t('travel.export.budget')}
                value={`${plan.budget_total} ${plan.budget_currency || 'CNY'}`}
              />
            )}
          </div>

          {plan.weather_summary && (
            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-800 dark:text-slate-100">
                {t('travel.export.weather')}
              </h3>
              <p className="break-words text-sm text-slate-600 dark:text-slate-400">{plan.weather_summary}</p>
            </section>
          )}

          <section className="space-y-3">
            <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">
              {t('travel.export.dailyItinerary')}
            </h3>
            {plan.daily_itinerary.map((day) => (
              <DaySection key={day.day} day={day} destination={plan.destination} />
            ))}
          </section>

          {navLinks.length > 0 && (
            <section>
              <div className="mb-2 flex items-center justify-between gap-3">
                <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">
                  {t('travel.export.navigationLinks')}
                </h3>
                <Button type="button" variant="ghost" size="sm" onClick={handleCopyNavLinks} className="h-8 gap-1.5 text-xs">
                  <Copy size={14} />
                  {copiedLinks ? t('travel.export.copiedPlan') : t('travel.export.copyNavLinks')}
                </Button>
              </div>
              <div className="space-y-2">
                {navLinks.map((item, index) => (
                  <a
                    key={`${item.name}-${index}`}
                    href={item.url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2 text-sm transition-colors hover:border-[#3B82F6] dark:border-slate-800"
                  >
                    <span className="min-w-0 break-words">
                      <span className="font-medium text-slate-800 dark:text-slate-100">{item.name}</span>
                      {item.address ? <span className="ml-2 text-slate-500">{item.address}</span> : null}
                    </span>
                    <ExternalLink size={14} className="shrink-0 text-[#3B82F6]" />
                  </a>
                ))}
              </div>
            </section>
          )}

          {plan.accommodations.length > 0 && (
            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-800 dark:text-slate-100">
                {t('travel.export.accommodations')}
              </h3>
              <ul className="space-y-2 text-sm text-slate-600 dark:text-slate-400">
                {plan.accommodations.map((item, index) => (
                  <li key={`${item.name}-${index}`} className="break-words">
                    <span className="font-medium text-slate-800 dark:text-slate-200">{item.name}</span>
                    {item.address ? ` — ${item.address}` : ''}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {plan.transport.length > 0 && (
            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-800 dark:text-slate-100">
                {t('travel.export.transport')}
              </h3>
              <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600 dark:text-slate-400">
                {plan.transport.map((item, index) => (
                  <li key={`${item}-${index}`} className="break-words">{item}</li>
                ))}
              </ul>
            </section>
          )}

          {plan.budget_breakdown.length > 0 && (
            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-800 dark:text-slate-100">
                {t('travel.export.budgetBreakdown')}
              </h3>
              <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 dark:bg-[#1E293B]/60">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium">{t('travel.export.category')}</th>
                      <th className="px-3 py-2 text-right font-medium">{t('travel.export.amount')}</th>
                      <th className="px-3 py-2 text-left font-medium">{t('travel.export.note')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {plan.budget_breakdown.map((item, index) => (
                      <tr key={`${item.category}-${index}`} className="border-t border-slate-200 dark:border-slate-800">
                        <td className="px-3 py-2">{item.category}</td>
                        <td className="px-3 py-2 text-right">
                          {item.amount != null ? `${item.amount} ${item.currency || 'CNY'}` : '—'}
                        </td>
                        <td className="px-3 py-2 text-slate-500">{item.note || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {plan.tips.length > 0 && (
            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-800 dark:text-slate-100">
                {t('travel.export.tips')}
              </h3>
              <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600 dark:text-slate-400">
                {plan.tips.map((tip, index) => (
                  <li key={`${tip}-${index}`} className="break-words">{tip}</li>
                ))}
              </ul>
            </section>
          )}

          <p className="text-xs text-slate-400">
            {plan.data_verified ? t('travel.export.verifiedFootnote') : t('travel.export.unverifiedFootnote')}
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
