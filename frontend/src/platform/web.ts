import type { Platform, PlatformPush, PushPermission, PushNowResult } from './types';
import type { InterviewPushSettings } from '@/services/api';
import { getInterviewTodayPlan } from '@/services/api';

function resolveBrowserMessage(plan: Awaited<ReturnType<typeof getInterviewTodayPlan>>): string | null {
  if (plan.push_message) return plan.push_message;
  const doc = plan.learning_doc;
  if (doc?.today_goal) {
    const bullets = (doc.reading_bullets || []).slice(0, 2);
    return bullets.length ? `${doc.today_goal}\n${bullets.map((b) => `· ${b}`).join('\n')}` : doc.today_goal;
  }
  if (doc?.section_title) return `今日学习：${doc.section_title}`;
  if (plan.tasks[0]?.message) return plan.tasks[0].message;
  if (plan.tasks[0]?.topic) return `今日主线：练「${plan.tasks[0].topic}」`;
  return null;
}

const webPush: PlatformPush = {
  // Scheduled push is desktop-only; immediate preview works in browser Notification.
  supportsPush: false,
  async requestPermission(): Promise<PushPermission> {
    if (!('Notification' in window)) return 'unsupported';
    if (Notification.permission === 'granted') return 'granted';
    if (Notification.permission === 'denied') return 'denied';
    const next = await Notification.requestPermission();
    if (next === 'granted') return 'granted';
    if (next === 'denied') return 'denied';
    return 'unsupported';
  },
  async syncScheduler() {
    // Web 端不提供定时系统推送
  },
  async stopScheduler() {
    // no-op
  },
  async pushNow(_settings?: InterviewPushSettings | null): Promise<PushNowResult> {
    if (!('Notification' in window)) {
      return { ok: false, reason: '当前浏览器不支持通知' };
    }
    let permission = Notification.permission;
    if (permission === 'default') {
      permission = await Notification.requestPermission();
    }
    if (permission !== 'granted') {
      return { ok: false, reason: '浏览器通知权限未开启' };
    }
    try {
      const plan = await getInterviewTodayPlan();
      const message = resolveBrowserMessage(plan);
      if (!message) {
        return { ok: false, reason: '今日暂无学习内容，请先设置目标达成时间并生成计划' };
      }
      new Notification('面试导航 · 今日学习计划', {
        body: message,
        tag: `interview-push-now-${Date.now()}`,
      });
      return { ok: true };
    } catch {
      return { ok: false, reason: '获取今日计划失败' };
    }
  },
};

export const platform: Platform = {
  isDesktop: false,
  push: webPush,
};
