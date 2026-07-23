import { Notification } from 'electron/main';
import type {
  InterviewPushSchedulerConfig,
  InterviewTodayPlanPayload,
  PushFrequency,
  PushNowResult,
} from './push-types';

function localDateKey(): string {
  return new Date().toISOString().slice(0, 10);
}

function shouldPushOnDate(frequency: PushFrequency, onDate = new Date()): boolean {
  const weekday = onDate.getDay();
  if (frequency === 'weekdays') return weekday >= 1 && weekday <= 5;
  if (frequency === 'weekends') return weekday === 0 || weekday === 6;
  return true;
}

function minutesUntilPush(pushTime: string): number | null {
  const [hour, minute] = pushTime.split(':').map(Number);
  if (Number.isNaN(hour) || Number.isNaN(minute)) return null;
  const now = new Date();
  const target = new Date();
  target.setHours(hour, minute, 0, 0);
  const diff = target.getTime() - now.getTime();
  if (diff < 0) return null;
  return Math.ceil(diff / 60_000);
}

function resolvePushMessage(today: InterviewTodayPlanPayload): string | null {
  if (today.push_message) return today.push_message;
  const doc = today.learning_doc;
  if (doc?.today_goal) {
    const bullets = (doc.reading_bullets || []).slice(0, 2);
    return bullets.length ? `${doc.today_goal}\n${bullets.map((b) => `· ${b}`).join('\n')}` : doc.today_goal;
  }
  if (doc?.section_title) return `今日学习：${doc.section_title}`;
  if (today.tasks[0]?.message) return today.tasks[0].message;
  if (today.tasks[0]?.topic) return `今日主线：练「${today.tasks[0].topic}」`;
  return null;
}

let config: InterviewPushSchedulerConfig | null = null;
let pollTimer: ReturnType<typeof setInterval> | null = null;
let pushTimer: ReturnType<typeof setTimeout> | null = null;
let lastPushDate: string | null = null;
let onNotificationClick: (() => void) | null = null;

async function fetchTodayPlan(apiBaseUrl: string, token: string | null): Promise<InterviewTodayPlanPayload | null> {
  if (!token) return null;
  const response = await fetch(`${apiBaseUrl}/interview/plan/today`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });
  if (!response.ok) return null;
  return response.json() as Promise<InterviewTodayPlanPayload>;
}

function showDesktopPush(message: string, topic: string, options?: { force?: boolean }) {
  if (!Notification.isSupported()) return;
  const today = localDateKey();
  if (!options?.force && lastPushDate === today) return;
  lastPushDate = today;

  const notification = new Notification({
    title: '面试导航 · 今日学习计划',
    body: message,
    silent: false,
  });
  notification.on('click', () => {
    onNotificationClick?.();
  });
  notification.show();
  void topic;
}

async function tick() {
  if (!config?.push_enabled || !config.token) return;
  const frequency = config.push_frequency || 'weekdays';
  if (!shouldPushOnDate(frequency)) return;

  try {
    const today = await fetchTodayPlan(config.apiBaseUrl, config.token);
    if (!today?.push_due_today || !today.push_message) return;

    const waitMinutes = minutesUntilPush(config.push_time);
    if (waitMinutes === null) {
      const hour = Number(config.push_time.split(':')[0]);
      if (new Date().getHours() >= hour) {
        showDesktopPush(today.push_message, today.tasks[0]?.topic ?? '训练');
      }
      return;
    }

    if (pushTimer) clearTimeout(pushTimer);
    pushTimer = setTimeout(() => {
      void fetchTodayPlan(config!.apiBaseUrl, config!.token).then((plan) => {
        if (plan?.push_message) {
          showDesktopPush(plan.push_message, plan.tasks[0]?.topic ?? '训练');
        }
      });
    }, waitMinutes * 60_000);
  } catch {
    // ignore transient API errors
  }
}

function clearTimers() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  if (pushTimer) {
    clearTimeout(pushTimer);
    pushTimer = null;
  }
}

export function startInterviewPushScheduler(
  next: InterviewPushSchedulerConfig,
  onClick?: () => void,
) {
  config = next;
  onNotificationClick = onClick ?? null;
  clearTimers();
  if (!next.push_enabled) return;
  void tick();
  pollTimer = setInterval(() => void tick(), 60_000);
}

export function stopInterviewPushScheduler() {
  config = null;
  onNotificationClick = null;
  clearTimers();
}

export function requestDesktopPushPermission(): 'granted' | 'denied' | 'unsupported' {
  if (!Notification.isSupported()) return 'unsupported';
  return 'granted';
}

/** Force-show today's learning push for preview / debugging. */
export async function pushInterviewNow(
  next?: InterviewPushSchedulerConfig | null,
): Promise<PushNowResult> {
  if (next) {
    config = { ...config, ...next, push_enabled: next.push_enabled ?? true };
  }
  if (!config?.token) {
    return { ok: false, reason: '未登录或缺少 API token' };
  }
  if (!Notification.isSupported()) {
    return { ok: false, reason: '当前系统不支持桌面通知' };
  }

  try {
    const today = await fetchTodayPlan(config.apiBaseUrl, config.token);
    if (!today) {
      return { ok: false, reason: '无法获取今日学习计划' };
    }
    const message = resolvePushMessage(today);
    if (!message) {
      return { ok: false, reason: '今日暂无学习内容，请先设置目标达成时间并生成计划' };
    }
    showDesktopPush(message, today.tasks[0]?.topic ?? '训练', { force: true });
    return { ok: true };
  } catch {
    return { ok: false, reason: '推送请求失败' };
  }
}
