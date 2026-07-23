import { useEffect } from 'react';
import { getPlatform } from '@/platform';
import type { InterviewPushSettings } from '@/services/api';
import type { PushFrequency } from '@/services/api';
import type { PushNowResult } from '@/platform/types';

export const PUSH_FREQUENCY_OPTIONS: { value: PushFrequency; label: string }[] = [
  { value: 'weekdays', label: '工作日（周一至周五）' },
  { value: 'daily', label: '每日' },
  { value: 'weekends', label: '周末' },
];

/** Sync interview push scheduler with the desktop main process. */
export function useInterviewPush(
  settings: InterviewPushSettings | null,
  enabled: boolean,
) {
  useEffect(() => {
    const platform = getPlatform();
    if (!platform.push.supportsPush) return undefined;

    void platform.push.syncScheduler(settings, enabled);
    return () => {
      void platform.push.stopScheduler();
    };
  }, [enabled, settings?.push_enabled, settings?.push_time, settings?.push_frequency]);
}

export async function requestInterviewPushPermission(): Promise<'granted' | 'denied' | 'unsupported'> {
  return getPlatform().push.requestPermission();
}

/** Immediately show today's learning push (preview / debug). */
export async function pushInterviewNow(
  settings?: InterviewPushSettings | null,
): Promise<PushNowResult> {
  return getPlatform().push.pushNow(settings);
}
