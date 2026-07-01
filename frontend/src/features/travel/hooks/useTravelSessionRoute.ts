/**
 * 旅行对话 URL ↔ sessionId 双向同步。
 * 路由形如 /travel/chat/:sessionId，刷新后从 URL 恢复会话。
 */

import { useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useChatStore } from '@/features/travel/stores/useChatStore';

export function useTravelSessionRoute() {
  const { sessionId: urlSessionId } = useParams<{ sessionId?: string }>();
  const navigate = useNavigate();
  const currentSessionId = useChatStore((state) => state.currentSessionId);
  const syncingFromUrlRef = useRef(false);

  // URL → Store（刷新、前进/后退、侧边栏切换会话）
  // 仅响应 URL 变化，避免 SSE 写入 sessionId 后因 store 变化误清空正在流式输出的消息
  useEffect(() => {
    const urlId = urlSessionId ?? null;

    syncingFromUrlRef.current = true;
    const {
      currentSessionId: storeSessionId,
      setCurrentSessionId,
      setMessages,
      startNewSession,
    } = useChatStore.getState();

    if (urlId) {
      if (storeSessionId !== urlId) {
        setCurrentSessionId(urlId);
        setMessages([]);
      }
    } else if (storeSessionId !== null) {
      startNewSession();
    }

    queueMicrotask(() => {
      syncingFromUrlRef.current = false;
    });
  }, [urlSessionId]);

  // Store → URL（首条消息创建会话、SSE 返回 session_id）
  useEffect(() => {
    if (syncingFromUrlRef.current) {
      return;
    }

    const storeSessionId = useChatStore.getState().currentSessionId;

    if (storeSessionId && storeSessionId !== urlSessionId) {
      navigate(`/travel/chat/${storeSessionId}`, { replace: true });
    } else if (!storeSessionId && urlSessionId) {
      navigate('/travel/chat', { replace: true });
    }
  }, [currentSessionId, urlSessionId, navigate]);
}
