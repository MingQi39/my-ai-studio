export type PushFrequency = 'daily' | 'weekdays' | 'weekends';

export interface InterviewPushSchedulerConfig {
  apiBaseUrl: string;
  token: string | null;
  push_enabled: boolean;
  push_time: string;
  push_frequency: PushFrequency;
}

export interface InterviewTodayPlanPayload {
  push_message: string | null;
  push_due_today: boolean;
  tasks: Array<{ topic: string; message?: string }>;
  learning_doc?: {
    today_goal?: string | null;
    section_title?: string | null;
    reading_bullets?: string[];
  } | null;
}

export interface PushNowResult {
  ok: boolean;
  reason?: string;
}
