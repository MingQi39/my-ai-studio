import { useCallback, useEffect } from 'react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

import { fetchFitnessTodaySummary } from '@/features/fitness/services/api/fitness';
import { useFitnessChatStore } from '@/features/fitness/stores/useFitnessChatStore';

export function useFitnessTodaySummary(enabled = true) {
  const { t } = useTranslation();
  const todaySummary = useFitnessChatStore((s) => s.todaySummary);
  const setTodaySummary = useFitnessChatStore((s) => s.setTodaySummary);
  const sessionListVersion = useFitnessChatStore((s) => s.sessionListVersion);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchFitnessTodaySummary(null);
      setTodaySummary(data);
      return data;
    } catch (error) {
      console.error(error);
      toast.error(t('fitness.panel.loadFailed'));
      return null;
    }
  }, [setTodaySummary, t]);

  useEffect(() => {
    if (!enabled) return;
    void refresh();
  }, [enabled, refresh, sessionListVersion]);

  return { todaySummary, refresh };
}
