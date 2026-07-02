import { useCallback, useEffect, useRef, useState } from 'react';

interface UseChatAutoScrollOptions {
  /** 内容变化时触发（如 messages、isGenerating） */
  deps?: unknown[];
  /** 距底部多少 px 内仍视为「在底部」 */
  bottomThresholdPx?: number;
  /** 是否启用（列表为空时可设为 false） */
  active?: boolean;
  /** 会话切换时重置滚动跟随状态（如 sessionId） */
  resetKey?: unknown;
}

/**
 * 聊天列表智能滚动：
 * - 用户在底部 → 新内容自动滚到底
 * - 用户向上翻看 → 停止自动滚动
 * - 调用 scrollToBottom() → 恢复跟随
 */
export function useChatAutoScroll(options: UseChatAutoScrollOptions = {}) {
  const { deps = [], bottomThresholdPx = 48, active = true, resetKey } = options;

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const scrollSentinelRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const isAtBottomRef = useRef(true);
  const userScrolledAwayRef = useRef(false);
  const isAutoScrollingRef = useRef(false);

  useEffect(() => {
    userScrolledAwayRef.current = false;
    isAtBottomRef.current = true;
    setIsAtBottom(true);
  }, [resetKey]);

  const checkIsAtBottom = useCallback(() => {
    const root = scrollContainerRef.current;
    if (!root) return true;
    return root.scrollHeight - root.scrollTop - root.clientHeight <= bottomThresholdPx;
  }, [bottomThresholdPx]);

  const scrollToBottom = useCallback(
    (behavior: ScrollBehavior = 'smooth') => {
      const root = scrollContainerRef.current;
      isAutoScrollingRef.current = true;
      if (root) {
        root.scrollTo({ top: root.scrollHeight, behavior });
      } else {
        scrollSentinelRef.current?.scrollIntoView({ behavior, block: 'end' });
      }
      userScrolledAwayRef.current = false;
      isAtBottomRef.current = true;
      setIsAtBottom(true);
      requestAnimationFrame(() => {
        isAutoScrollingRef.current = false;
      });
    },
    [],
  );

  useEffect(() => {
    const root = scrollContainerRef.current;
    if (!root || !active) return;

    const onScroll = () => {
      if (isAutoScrollingRef.current) return;
      const atBottom = checkIsAtBottom();
      isAtBottomRef.current = atBottom;
      setIsAtBottom(atBottom);
      if (!atBottom) {
        userScrolledAwayRef.current = true;
      }
    };

    const onUserScrollIntent = () => {
      if (!isAutoScrollingRef.current) {
        userScrolledAwayRef.current = true;
      }
    };

    root.addEventListener('scroll', onScroll, { passive: true });
    root.addEventListener('wheel', onUserScrollIntent, { passive: true });
    root.addEventListener('touchstart', onUserScrollIntent, { passive: true });

    return () => {
      root.removeEventListener('scroll', onScroll);
      root.removeEventListener('wheel', onUserScrollIntent);
      root.removeEventListener('touchstart', onUserScrollIntent);
    };
  }, [active, checkIsAtBottom]);

  useEffect(() => {
    if (!active) return;
    if (userScrolledAwayRef.current && !checkIsAtBottom()) return;

    isAutoScrollingRef.current = true;
    const root = scrollContainerRef.current;

    const runScroll = () => {
      if (root) {
        root.scrollTo({ top: root.scrollHeight, behavior: 'auto' });
      } else {
        scrollSentinelRef.current?.scrollIntoView({ behavior: 'auto', block: 'end' });
      }
      isAutoScrollingRef.current = false;
      isAtBottomRef.current = true;
      setIsAtBottom(true);
    };

    requestAnimationFrame(() => {
      requestAnimationFrame(runScroll);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deps supplied by caller
  }, deps);

  return {
    scrollContainerRef,
    scrollSentinelRef,
    isAtBottom,
    showJumpButton: !isAtBottom,
    scrollToBottom,
  };
}
