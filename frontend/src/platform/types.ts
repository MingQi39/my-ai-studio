import type { InterviewPushSettings } from '@/services/api';

export type PushPermission = 'granted' | 'denied' | 'unsupported';

export interface PushNowResult {
  ok: boolean;
  reason?: string;
}

export interface PlatformPush {
  readonly supportsPush: boolean;
  requestPermission(): Promise<PushPermission>;
  syncScheduler(settings: InterviewPushSettings | null, enabled: boolean): Promise<void>;
  stopScheduler(): Promise<void>;
  pushNow(settings?: InterviewPushSettings | null): Promise<PushNowResult>;
}

export interface Platform {
  readonly isDesktop: boolean;
  readonly push: PlatformPush;
}
