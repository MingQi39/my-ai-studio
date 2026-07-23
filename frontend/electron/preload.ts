import { contextBridge, ipcRenderer } from 'electron';
import type { InterviewPushSchedulerConfig, PushNowResult } from './push-types';

export type PushPermission = 'granted' | 'denied' | 'unsupported';

const electronAPI = {
  isDesktop: true as const,
  push: {
    supportsPush: true as const,
    requestPermission: (): Promise<PushPermission> => ipcRenderer.invoke('push:request-permission'),
    syncScheduler: (config: InterviewPushSchedulerConfig): Promise<void> =>
      ipcRenderer.invoke('push:sync-scheduler', config),
    stopScheduler: (): Promise<void> => ipcRenderer.invoke('push:stop-scheduler'),
    pushNow: (config?: InterviewPushSchedulerConfig | null): Promise<PushNowResult> =>
      ipcRenderer.invoke('push:push-now', config),
  },
};

contextBridge.exposeInMainWorld('electronAPI', electronAPI);

export type ElectronAPI = typeof electronAPI;
