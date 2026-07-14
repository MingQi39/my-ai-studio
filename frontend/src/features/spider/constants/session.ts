export const SPIDER_ACTIVE_SESSION_KEY = 'spider:activeSessionId';
export const SPIDER_DRAFT_TARGET_URL_KEY = 'spider:draftTargetUrl';
export const SPIDER_GENERATING_SESSION_KEY = 'spider:generatingSessionId';

export function spiderTargetUrlStorageKey(sessionId: string) {
  return `spider:targetUrl:${sessionId}`;
}
