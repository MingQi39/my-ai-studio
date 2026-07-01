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
  const pendingUrlSyncRef = useRef(Boolean(urlSessionId));

  // URL → Store（刷新、前进/后退、侧边栏切换会话）
  useEffect(() => {
    const urlId = urlSessionId ?? null;

    if (urlId === currentSessionId) {
      pendingUrlSyncRef.current = false;
      return;
    }

    syncingFromUrlRef.current = true;
    const { setCurrentSessionId, setMessages, startNewSession } =
      useChatStore.getState();

    if (urlId) {
      setCurrentSessionId(urlId);
      setMessages([]);
    } else {
      startNewSession();
    }

    queueMicrotask(() => {
      syncingFromUrlRef.current = false;
    });
  }, [urlSessionId, currentSessionId]);

  // Store → URL（首条消息创建会话、SSE 返回 session_id）
  useEffect(() => {
    if (syncingFromUrlRef.current || pendingUrlSyncRef.current) {
      return;
    }

    if (currentSessionId && currentSessionId !== urlSessionId) {
      navigate(`/travel/chat/${currentSessionId}`, { replace: true });
    } else if (!currentSessionId && urlSessionId) {
      navigate('/travel/chat', { replace: true });
    }
  }, [currentSessionId, urlSessionId, navigate]);
}
