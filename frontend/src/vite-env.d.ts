/// <reference types="vite/client" />

import type { InterviewPushSchedulerConfig, PushNowResult } from '../electron/push-types';

type PushPermission = 'granted' | 'denied' | 'unsupported';

interface ElectronAPI {
  isDesktop: true;
  push: {
    supportsPush: true;
    requestPermission(): Promise<PushPermission>;
    syncScheduler(config: InterviewPushSchedulerConfig): Promise<void>;
    stopScheduler(): Promise<void>;
    pushNow(config?: InterviewPushSchedulerConfig | null): Promise<PushNowResult>;
  };
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_IS_ELECTRON?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}

export {};
