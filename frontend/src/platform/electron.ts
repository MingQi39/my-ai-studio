import type { Platform, PlatformPush, PushPermission, PushNowResult } from './types';
import type { InterviewPushSettings } from '@/services/api';
import { getApiBaseUrl, getToken } from '@/services/api';

function getElectronAPI() {
  const api = window.electronAPI;
  if (!api?.isDesktop) {
    throw new Error('Electron API is not available');
  }
  return api;
}

const electronPush: PlatformPush = {
  supportsPush: true,
  async requestPermission(): Promise<PushPermission> {
    return getElectronAPI().push.requestPermission();
  },
  async syncScheduler(settings: InterviewPushSettings | null, enabled: boolean) {
    const api = getElectronAPI();
    if (!enabled || !settings?.push_enabled) {
      await api.push.stopScheduler();
      return;
    }
    await api.push.syncScheduler({
      apiBaseUrl: getApiBaseUrl(),
      token: getToken(),
      push_enabled: settings.push_enabled,
      push_time: settings.push_time,
      push_frequency: settings.push_frequency || 'weekdays',
    });
  },
  async stopScheduler() {
    await getElectronAPI().push.stopScheduler();
  },
  async pushNow(settings?: InterviewPushSettings | null): Promise<PushNowResult> {
    return getElectronAPI().push.pushNow({
      apiBaseUrl: getApiBaseUrl(),
      token: getToken(),
      push_enabled: settings?.push_enabled ?? true,
      push_time: settings?.push_time || '21:00',
      push_frequency: settings?.push_frequency || 'weekdays',
    });
  },
};

export const platform: Platform = {
  isDesktop: true,
  push: electronPush,
};
