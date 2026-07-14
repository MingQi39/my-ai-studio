import { useCallback } from 'react';

import {
  fetchSpiderWorkspace,
  type SpiderWorkspaceFile,
} from '@/features/spider/services/api/spider';
import { useSpiderChatStore } from '@/features/spider/stores/useSpiderChatStore';

export function useSpiderWorkspace() {
  const currentSessionId = useSpiderChatStore((s) => s.currentSessionId);
  const workspaceFiles = useSpiderChatStore((s) => s.workspaceFiles);
  const setWorkspaceFiles = useSpiderChatStore((s) => s.setWorkspaceFiles);

  const refreshWorkspace = useCallback(async () => {
    if (!currentSessionId) {
      setWorkspaceFiles([]);
      return;
    }
    try {
      const response = await fetchSpiderWorkspace(currentSessionId);
      setWorkspaceFiles(response.files);
    } catch (error) {
      console.error(error);
    }
  }, [currentSessionId, setWorkspaceFiles]);

  const applyWorkspaceFiles = useCallback(
    (files: SpiderWorkspaceFile[]) => {
      setWorkspaceFiles(files);
    },
    [setWorkspaceFiles],
  );

  return { workspaceFiles, refreshWorkspace, applyWorkspaceFiles };
}
