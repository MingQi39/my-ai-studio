import { useCallback, useEffect, useRef, useState } from 'react';

interface UseChatAutoScrollOptions {
  /** 内容变化时触发（如 messages、isGenerating） */
  deps?: unknown[];
  /** 距底部多少 px 内仍视为「在底部」 */
  bottomThresholdPx?: number;
  /** 是否启用（列表为空时可设为 false） */
  active?: boolean;
}

/**
 * 聊天列表智能滚动：
 * - 用户在底部 → 新内容自动滚到底
 * - 用户向上翻看 → 停止自动滚动
 * - 调用 scrollToBottom() → 恢复跟随
 */
export function useChatAutoScroll(options: UseChatAutoScrollOptions = {}) {
  const { deps = [], bottomThresholdPx = 48, active = true } = options;

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const scrollSentinelRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const isAtBottomRef = useRef(true);

  useEffect(() => {
    isAtBottomRef.current = isAtBottom;
  }, [isAtBottom]);

  useEffect(() => {
    if (!active) return;

    const root = scrollContainerRef.current;
    const sentinel = scrollSentinelRef.current;
    if (!root || !sentinel) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsAtBottom(entry.isIntersecting);
      },
      {
        root,
        threshold: 0,
        rootMargin: `0px 0px ${bottomThresholdPx}px 0px`,
      },
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [bottomThresholdPx, active]);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    scrollSentinelRef.current?.scrollIntoView({ behavior, block: 'end' });
  }, []);

  useEffect(() => {
    if (!isAtBottomRef.current) return;
    scrollSentinelRef.current?.scrollIntoView({ behavior: 'auto', block: 'end' });
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
