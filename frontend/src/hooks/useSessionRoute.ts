/**
 * 主工作区 URL ↔ sessionId 双向同步。
 * 路由形如 /session/:sessionId，刷新后从 URL 恢复会话。
 */

import { useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

export function useSessionRoute() {
  const { sessionId: urlSessionId } = useParams<{ sessionId?: string }>();
  const navigate = useNavigate();

  const currentSessionId = urlSessionId ?? null;

  const setCurrentSessionId = useCallback(
    (sessionId: string | null) => {
      if (sessionId) {
        navigate(`/session/${sessionId}`, { replace: true });
      } else {
        navigate('/', { replace: true });
      }
    },
    [navigate],
  );

  return { currentSessionId, setCurrentSessionId };
}
