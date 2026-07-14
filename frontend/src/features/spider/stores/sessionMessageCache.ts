/** Minimal message shape for session cache helpers (compatible with StudioChatMessage). */
export type CacheableChatMessage = {
  id: string;
  [key: string]: unknown;
};

export type SpiderMessageCache<T extends CacheableChatMessage = CacheableChatMessage> = Record<
  string,
  T[]
>;

/** Snapshot current messages into the cache when leaving a session. */
export function stashSessionMessages<T extends CacheableChatMessage>(
  cache: SpiderMessageCache<T>,
  sessionId: string | null,
  messages: T[],
): SpiderMessageCache<T> {
  if (!sessionId) return cache;
  return { ...cache, [sessionId]: messages };
}

/**
 * Resolve what to show after switching sessions.
 * Prefer the in-memory cache (keeps in-flight agent UI) over clearing.
 */
export function resolveMessagesAfterSwitch<T extends CacheableChatMessage>(
  cache: SpiderMessageCache<T>,
  nextSessionId: string,
): T[] {
  return cache[nextSessionId] ?? [];
}

/** Apply a message patch to a list (used for live stream + off-screen cache). */
export function applyMessagePatch<T extends CacheableChatMessage>(
  messages: T[],
  id: string,
  updates: Partial<T>,
): T[] {
  return messages.map((msg) => (msg.id === id ? { ...msg, ...updates } : msg));
}

/**
 * While an agent run is active, stream patches must update either the live
 * messages (if viewing that session) or the cached copy (if user switched away).
 */
export function patchGeneratingMessages<T extends CacheableChatMessage>(input: {
  messages: T[];
  messageCache: SpiderMessageCache<T>;
  currentSessionId: string | null;
  generatingSessionId: string | null;
  messageId: string;
  updates: Partial<T>;
}): { messages: T[]; messageCache: SpiderMessageCache<T> } {
  const {
    messages,
    messageCache,
    currentSessionId,
    generatingSessionId,
    messageId,
    updates,
  } = input;

  if (generatingSessionId && currentSessionId === generatingSessionId) {
    const next = applyMessagePatch(messages, messageId, updates);
    return {
      messages: next,
      messageCache: { ...messageCache, [generatingSessionId]: next },
    };
  }

  if (generatingSessionId && messageCache[generatingSessionId]) {
    return {
      messages,
      messageCache: {
        ...messageCache,
        [generatingSessionId]: applyMessagePatch(
          messageCache[generatingSessionId],
          messageId,
          updates,
        ),
      },
    };
  }

  return {
    messages: applyMessagePatch(messages, messageId, updates),
    messageCache,
  };
}
