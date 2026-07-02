import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import type { ChatToolsState } from '@/components/ControlPanel';
import { applyStudioChatStreamChunk } from '@/hooks/studioChat/applyStreamChunk';
import {
  createStudioAssistantPlaceholder,
  useStudioChatStream,
} from '@/hooks/useStudioChatStream';
import {
  clearRecoveryPrompts,
  getLastMessageFingerprint,
  hasRecoverableAssistantProgress,
  looksLikeInProgressGeneration,
  mapApiMessagesToStudio,
  markStreamRecoveryPrompt,
  needsStreamRecovery,
} from '@/hooks/studioChat/mapApiMessages';
import { pollGenerationFromDb } from '@/hooks/studioChat/pollGeneration';
import {
  clearAssistantThinkingState,
  prepareRecoveringAssistantUI,
} from '@/hooks/studioChat/prepareRecoveringUI';
import type { StudioChatMessage } from '@/hooks/studioChat/types';
import {
  createSession,
  deleteSession as apiDeleteSession,
  getSessionMessages,
  getStreamStatus,
  startResumeStream,
  startRetryStreamChat,
  listSessions,
  updateSession,
  uploadFile,
  type ChatRequest,
  type ChatStreamChunk,
  type SessionResponse,
} from '@/services/api';

export type { StudioChatMessage } from '@/hooks/studioChat/types';

export type UploadedStudioImage = {
  id: string;
  url: string;
  name: string;
  file: File;
  uploading?: boolean;
};

export type UseStudioChatOptions = {
  currentSessionId: string | null;
  onSessionChange: (sessionId: string | null) => void;
  sessionRefreshTrigger?: number;
  onSessionsChange?: () => void;
  hasModelConfig: boolean | null;
  onOpenConnectionModal: () => void;
  enableReasoning: boolean;
  systemPrompt?: string;
  modelConfigId?: string | null;
  toolsState: ChatToolsState;
};

export function useStudioChat({
  currentSessionId,
  onSessionChange,
  sessionRefreshTrigger,
  onSessionsChange,
  hasModelConfig,
  onOpenConnectionModal,
  enableReasoning,
  systemPrompt,
  modelConfigId,
  toolsState,
}: UseStudioChatOptions) {
  const { t } = useTranslation();
  const [input, setInput] = useState('');
  const [uploadedImages, setUploadedImages] = useState<UploadedStudioImage[]>([]);
  const [messages, setMessages] = useState<StudioChatMessage[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [isFirstMessage, setIsFirstMessage] = useState(true);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState<string | null>(null);

  const { runStream, cancelStream } = useStudioChatStream();
  const skipLoadMessagesRef = useRef(false);

  const loadSessions = useCallback(async () => {
    try {
      setIsLoadingSessions(true);
      const response = await listSessions(1, 50, false);
      setSessions(response.items);
    } catch (error) {
      console.error('Failed to load sessions:', error);
      toast.error(t('workspace.loadSessionsFailed'));
    } finally {
      setIsLoadingSessions(false);
    }
  }, [t]);

  const loadSessionMessages = useCallback(
    async (sessionId: string) => {
      try {
        const apiMessages = await getSessionMessages(sessionId, 100);
        const localMessages = mapApiMessagesToStudio(apiMessages);
        setMessages(localMessages);
        setIsFirstMessage(localMessages.length === 0);
        return localMessages;
      } catch (error) {
        console.error('Failed to load messages:', error);
        toast.error(t('workspace.loadMessagesFailed'));
        return null;
      }
    },
    [t],
  );

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (sessionRefreshTrigger !== undefined && sessionRefreshTrigger > 0) {
      loadSessions();
    }
  }, [sessionRefreshTrigger, loadSessions]);

  const resumeCancelRef = useRef<(() => void) | null>(null);
  const pollGenerationRef = useRef<{ cancel: () => void } | null>(null);
  const sessionRecoveryGenerationRef = useRef(0);
  const tryResumeStreamRef = useRef<
    (sessionId: string, loadedMessages?: StudioChatMessage[], pollAutoRetry?: boolean) => Promise<void>
  >(async () => {});

  const isStreamAlreadyEndedError = (error: unknown): boolean => {
    const message = error instanceof Error ? error.message : String(error);
    return message.includes('404') && message.toLowerCase().includes('no active stream');
  };

  const pollForGenerationUpdates = useCallback(
    async (
      sessionId: string,
      snapshot: StudioChatMessage[],
      options?: {
        allowAutoRetry?: boolean;
        assistantMessageId?: string | null;
        suppressRecoveryPrompt?: boolean;
        maxAttempts?: number;
      },
    ) => {
      pollGenerationRef.current?.cancel();

      let cancelled = false;
      pollGenerationRef.current = {
        cancel: () => {
          cancelled = true;
        },
      };

      setIsGenerating(true);
      setMessages(prepareRecoveringAssistantUI(clearRecoveryPrompts(snapshot), options?.assistantMessageId));

      const result = await pollGenerationFromDb({
        sessionId,
        onMessagesUpdate: (nextMessages) => {
          setMessages(() => {
            const merged = clearRecoveryPrompts(nextMessages);
            if (!looksLikeInProgressGeneration(merged)) return merged;

            const lastAssistant = [...merged].reverse().find((message) => message.role === 'assistant');
            const assistantId = lastAssistant?.id ?? options?.assistantMessageId;
            return prepareRecoveringAssistantUI(merged, assistantId);
          });
        },
        isCancelled: () => cancelled,
        maxAttempts: options?.maxAttempts,
      });

      pollGenerationRef.current = null;
      if (cancelled) return;

      if (result === 'resumed') {
        await tryResumeStreamRef.current(sessionId, snapshot, false);
        return;
      }

      if (result === 'completed') {
        setIsGenerating(false);
        return;
      }

      const messages = (await loadSessionMessages(sessionId)) ?? snapshot;
      if (!looksLikeInProgressGeneration(messages)) {
        setIsGenerating(false);
        return;
      }

      if (options?.allowAutoRetry) {
        await tryResumeStreamRef.current(sessionId, messages, false);
        return;
      }

      if (options?.suppressRecoveryPrompt) {
        setIsGenerating(false);
        return;
      }

      setMessages((prev) => markStreamRecoveryPrompt(clearAssistantThinkingState(prev.length ? prev : messages)));
      setIsGenerating(false);
    },
    [loadSessionMessages],
  );

  const handleResumeStreamError = useCallback(
    async (sessionId: string, aiMsgId: string | null, error: unknown, snapshot?: StudioChatMessage[]) => {
      setIsGenerating(false);

      if (aiMsgId) {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === aiMsgId ? { ...message, isThinking: false } : message,
          ),
        );
      }

      const messages = snapshot ?? (await loadSessionMessages(sessionId));
      if (!messages || !looksLikeInProgressGeneration(messages)) return;

      if (isStreamAlreadyEndedError(error)) {
        toast.info(t('workspace.streamResumeEnded'));
      } else {
        console.error('Resume stream error:', error);
      }

      await pollForGenerationUpdates(sessionId, messages, {
        allowAutoRetry: true,
        assistantMessageId: aiMsgId,
      });
    },
    [loadSessionMessages, pollForGenerationUpdates, t],
  );

  const resumeStreamForMessage = useCallback(
    async (sessionId: string, aiMsgId: string, snapshot: StudioChatMessage[]) => {
      setIsGenerating(true);
      setMessages(prepareRecoveringAssistantUI(snapshot, aiMsgId));

      const buffers = { thinking: '', content: '' };

      await new Promise<void>((resolve, reject) => {
        const { promise, cancel } = startResumeStream(
          sessionId,
          (chunk: ChatStreamChunk) => {
            setMessages((prev) =>
              prev.map((message) =>
                message.id === aiMsgId ? applyStudioChatStreamChunk(message, chunk, buffers) : message,
              ),
            );
          },
          (error) => {
            reject(error);
          },
          () => {
            setIsGenerating(false);
            setMessages((prev) => clearAssistantThinkingState(prev));
            loadSessions();
            onSessionsChange?.();
            resolve();
          },
        );

        resumeCancelRef.current = cancel;
        void promise.catch(reject);
      });
    },
    [loadSessions, onSessionsChange],
  );

  const regenerateIncompleteResponse = useCallback(
    async (sessionId: string, snapshot: StudioChatMessage[]) => {
      const aiMsgId = `retry-${Date.now()}`;
      setMessages(() => {
        const trimmed = clearRecoveryPrompts(snapshot);
        const last = trimmed[trimmed.length - 1];
        const withoutDeadAssistant =
          last?.role === 'assistant' &&
          (last.isComplete === false || !last.content.trim())
            ? trimmed.slice(0, -1)
            : trimmed;
        return [...withoutDeadAssistant, createStudioAssistantPlaceholder(aiMsgId)];
      });

      setIsGenerating(true);
      const buffers = { thinking: '', content: '' };

      await new Promise<void>((resolve, reject) => {
        const { promise, cancel } = startRetryStreamChat(
          sessionId,
          {
            stream: true,
            enable_reasoning: enableReasoning,
            system_prompt: systemPrompt || undefined,
            model_config_id: modelConfigId || undefined,
            tools_config: toolsState,
          },
          (chunk: ChatStreamChunk) => {
            setMessages((prev) =>
              prev.map((message) =>
                message.id === aiMsgId ? applyStudioChatStreamChunk(message, chunk, buffers) : message,
              ),
            );
          },
          (error) => {
            reject(error);
          },
          () => {
            resolve();
          },
        );

        resumeCancelRef.current = cancel;
        void promise.catch(reject);
      });

      const next = await loadSessionMessages(sessionId);
      if (next) {
        setMessages(next);
      }
      resumeCancelRef.current = null;
    },
    [enableReasoning, loadSessionMessages, modelConfigId, systemPrompt, toolsState],
  );

  const handleRetryStreamRecovery = useCallback(async () => {
    if (!currentSessionId || isGenerating) return;

    resumeCancelRef.current?.();
    pollGenerationRef.current?.cancel();
    setIsGenerating(true);

    try {
      let messages = (await loadSessionMessages(currentSessionId)) ?? [];
      setMessages(clearAssistantThinkingState(clearRecoveryPrompts(messages)));

      const status = await getStreamStatus(currentSessionId);
      if (status.is_streaming && status.message_id) {
        try {
          await resumeStreamForMessage(currentSessionId, status.message_id, messages);
          messages = (await loadSessionMessages(currentSessionId)) ?? messages;
          if (!needsStreamRecovery(messages)) {
            setMessages(messages);
            return;
          }
        } catch (error) {
          if (!isStreamAlreadyEndedError(error)) {
            console.error('Resume during recovery failed:', error);
          }
        }
      }

      const last = messages[messages.length - 1];
      if (hasRecoverableAssistantProgress(last)) {
        await pollForGenerationUpdates(currentSessionId, messages, {
          allowAutoRetry: false,
          suppressRecoveryPrompt: true,
          maxAttempts: 5,
        });
        messages = (await loadSessionMessages(currentSessionId)) ?? messages;
        if (!needsStreamRecovery(messages)) {
          setMessages(messages);
          return;
        }
      }

      if (!needsStreamRecovery(messages)) {
        setMessages(messages);
        return;
      }

      await regenerateIncompleteResponse(currentSessionId, messages);
      loadSessions();
      onSessionsChange?.();
    } catch (error) {
      console.error('Stream recovery failed:', error);
      const message = error instanceof Error ? error.message : String(error);
      toast.error(t('workspace.chatError', { message }));
      const next = await loadSessionMessages(currentSessionId);
      if (next) {
        setMessages(markStreamRecoveryPrompt(clearAssistantThinkingState(next)));
      }
    } finally {
      setIsGenerating(false);
    }
  }, [
    currentSessionId,
    isGenerating,
    loadSessionMessages,
    loadSessions,
    onSessionsChange,
    pollForGenerationUpdates,
    regenerateIncompleteResponse,
    resumeStreamForMessage,
    t,
  ]);

  // 刷新恢复：加载历史消息后检测活跃流并重连
  const tryResumeStream = useCallback(
    async (sessionId: string, loadedMessages?: StudioChatMessage[], pollAutoRetry = false) => {
      const snapshot = loadedMessages ?? (await loadSessionMessages(sessionId));
      if (!snapshot) return;

      let aiMsgId: string | null = null;

      try {
        const status = await getStreamStatus(sessionId);
        if (!status.is_streaming || !status.message_id) {
          const last = snapshot[snapshot.length - 1];
          if (hasRecoverableAssistantProgress(last) && looksLikeInProgressGeneration(snapshot)) {
            await pollForGenerationUpdates(sessionId, snapshot, { allowAutoRetry: pollAutoRetry });
            return;
          }

          if (needsStreamRecovery(snapshot)) {
            setMessages(markStreamRecoveryPrompt(clearAssistantThinkingState(snapshot)));
            setIsGenerating(false);
          }
          return;
        }

        aiMsgId = status.message_id;
        setIsGenerating(true);
        setMessages(prepareRecoveringAssistantUI(snapshot, aiMsgId));

        const buffers = { thinking: '', content: '' };

        const { promise, cancel } = startResumeStream(
          sessionId,
          (chunk: ChatStreamChunk) => {
            setMessages((prev) =>
              prev.map((message) =>
                message.id === aiMsgId
                  ? applyStudioChatStreamChunk(message, chunk, buffers)
                  : message,
              ),
            );
          },
          (error) => {
            void handleResumeStreamError(sessionId, aiMsgId, error, snapshot);
          },
          () => {
            setIsGenerating(false);
            setMessages((prev) => clearAssistantThinkingState(prev));
            loadSessions();
            onSessionsChange?.();
          },
        );

        resumeCancelRef.current = cancel;
        await promise;
      } catch (error) {
        await handleResumeStreamError(sessionId, aiMsgId, error, snapshot);
      }
    },
    [handleResumeStreamError, loadSessionMessages, loadSessions, onSessionsChange, pollForGenerationUpdates],
  );

  tryResumeStreamRef.current = tryResumeStream;

  useEffect(() => {
    if (!currentSessionId) {
      setMessages([]);
      setIsFirstMessage(true);
      setIsGenerating(false);
      return;
    }

    if (skipLoadMessagesRef.current) {
      skipLoadMessagesRef.current = false;
      return;
    }

    const generation = ++sessionRecoveryGenerationRef.current;

    void (async () => {
      const messages = await loadSessionMessages(currentSessionId);
      if (generation !== sessionRecoveryGenerationRef.current || !messages) return;
      await tryResumeStreamRef.current(currentSessionId, messages, true);
    })();

    return () => {
      sessionRecoveryGenerationRef.current += 1;
      resumeCancelRef.current?.();
      resumeCancelRef.current = null;
      pollGenerationRef.current?.cancel();
      pollGenerationRef.current = null;
    };
  }, [currentSessionId, loadSessionMessages]);

  const handleNewSession = async () => {
    try {
      const session = await createSession({
        title: t('workspace.newChat'),
      });
      setSessions((prev) => [session, ...prev]);
      skipLoadMessagesRef.current = true;
      onSessionChange(session.id);
      setMessages([]);
      setIsFirstMessage(true);
      toast.success(t('workspace.newChatCreated'));
      onSessionsChange?.();
    } catch (error) {
      console.error('Failed to create session:', error);
      toast.error(t('workspace.newChatFailed'));
    }
  };

  const handleDeleteSession = (sessionId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    setSessionToDelete(sessionId);
    setIsDeleteDialogOpen(true);
  };

  const confirmDeleteSession = async () => {
    if (!sessionToDelete) return;
    try {
      await apiDeleteSession(sessionToDelete);
      setSessions((prev) => prev.filter((session) => session.id !== sessionToDelete));
      if (currentSessionId === sessionToDelete) {
        onSessionChange(null);
        setMessages([]);
      }
      toast.success(t('sidebar.sessionDeleted'));
      onSessionsChange?.();
    } catch (error) {
      console.error('Failed to delete session:', error);
      toast.error(t('sidebar.deleteFailed'));
    } finally {
      setIsDeleteDialogOpen(false);
      setSessionToDelete(null);
    }
  };

  const handleSelectSession = (sessionId: string) => {
    onSessionChange(sessionId);
  };

  const handleSendMessage = async () => {
    if (!input.trim() && uploadedImages.length === 0) return;

    if (hasModelConfig === false) {
      toast.error(t('workspace.needModelConfig'));
      onOpenConnectionModal();
      return;
    }

    if (hasModelConfig === null) {
      toast.info(t('workspace.loadingConfig'));
      return;
    }

    if (uploadedImages.some((image) => image.uploading)) {
      toast.info(t('workspace.waitingUpload'));
      return;
    }

    const messageContent = input.trim();
    let sessionId = currentSessionId;

    if (!sessionId) {
      try {
        const title =
          messageContent.length > 20
            ? `${messageContent.substring(0, 20)}...`
            : messageContent || t('workspace.imageDialog');
        const session = await createSession({ title });
        setSessions((prev) => [session, ...prev]);
        sessionId = session.id;
        skipLoadMessagesRef.current = true;
        onSessionChange(sessionId);
      } catch (error) {
        console.error('Failed to create session:', error);
        toast.error(t('workspace.createSessionFailed'));
        return;
      }
    } else if (isFirstMessage && messageContent) {
      try {
        const title =
          messageContent.length > 20 ? `${messageContent.substring(0, 20)}...` : messageContent;
        await updateSession(sessionId, { title });
        setSessions((prev) => prev.map((session) => (session.id === sessionId ? { ...session, title } : session)));
        onSessionsChange?.();
      } catch (error) {
        console.error('Failed to update session title:', error);
      }
    }

    const userMsg: StudioChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: messageContent,
      images:
        uploadedImages.length > 0
          ? uploadedImages.map((image) => ({
              id: image.id,
              url: image.url,
              name: image.name,
            }))
          : undefined,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    const currentImages = [...uploadedImages];
    setUploadedImages([]);
    setIsGenerating(true);
    setIsFirstMessage(false);

    const aiMsgId = (Date.now() + 1).toString();
    setMessages((prev) => [...prev, createStudioAssistantPlaceholder(aiMsgId)]);

    const chatRequest: ChatRequest = {
      session_id: sessionId,
      message: messageContent,
      file_ids: currentImages.length > 0 ? currentImages.map((image) => image.id) : undefined,
      stream: true,
      enable_reasoning: enableReasoning,
      system_prompt: systemPrompt || undefined,
      model_config_id: modelConfigId || undefined,
      tools_config: toolsState,
    };

    await runStream({
      chatRequest,
      aiMsgId,
      setMessages,
      formatErrorContent: (message) => t('workspace.errorPrefix', { message }),
      onError: (error) => {
        console.error('Chat error:', error);
        toast.error(t('workspace.chatError', { message: error.message }));
        setIsGenerating(false);
      },
      onComplete: () => {
        setIsGenerating(false);
        loadSessions();
        onSessionsChange?.();
      },
      onCancel: () => {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === aiMsgId && message.isThinking
              ? { ...message, isThinking: false }
              : message,
          ),
        );
        setIsGenerating(false);
      },
    });
  };

  const handleStopGeneration = () => {
    cancelStream();
    resumeCancelRef.current?.();
    resumeCancelRef.current = null;
    pollGenerationRef.current?.cancel();
    pollGenerationRef.current = null;
    setIsGenerating(false);
    setMessages((prev) => clearAssistantThinkingState(clearRecoveryPrompts(prev)));
  };

  const handleAddFile = async (type: 'image' | 'file' | 'video') => {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';

    if (type === 'image') {
      fileInput.accept = 'image/*';
    } else if (type === 'video') {
      fileInput.accept = 'video/*,audio/*';
    } else {
      fileInput.accept = '*/*';
    }

    fileInput.onchange = async (event) => {
      const file = (event.target as HTMLInputElement).files?.[0];
      if (!file) return;

      if (type === 'image') {
        try {
          const tempId = `temp_${Date.now()}`;
          const tempUrl = URL.createObjectURL(file);
          setUploadedImages((prev) => [
            ...prev,
            {
              id: tempId,
              url: tempUrl,
              name: file.name,
              file,
              uploading: true,
            },
          ]);

          const uploadedFile = await uploadFile(file);

          setUploadedImages((prev) =>
            prev.map((image) =>
              image.id === tempId
                ? { ...image, id: uploadedFile.id, url: uploadedFile.url, uploading: false }
                : image,
            ),
          );

          toast.success(t('workspace.imageUploaded'));
        } catch (error) {
          console.error('Upload failed:', error);
          toast.error(t('workspace.imageUploadFailed'));
          setUploadedImages((prev) => prev.filter((image) => !image.uploading));
        }
      } else {
        toast.info(t('workspace.unsupportedFile'));
      }
    };

    fileInput.click();
  };

  const handleExportCode = async () => {
    const snippets: string[] = [];

    for (const message of messages) {
      if (message.tool?.code?.trim()) {
        snippets.push(message.tool.code.trim());
      }

      for (const run of message.toolRuns ?? []) {
        if (run.tool_name === 'execute_python') {
          const code = String(run.tool_input?.code ?? '').trim();
          if (code) snippets.push(code);
        }
      }

      if (message.content) {
        const fenced = message.content.matchAll(/```(?:[\w+-]*)?\n([\s\S]*?)```/g);
        for (const match of fenced) {
          const block = match[1]?.trim();
          if (block) snippets.push(block);
        }
      }
    }

    const unique = [...new Set(snippets)];
    if (unique.length === 0) {
      toast.error(t('workspace.codeExportEmpty'));
      return;
    }

    try {
      await navigator.clipboard.writeText(unique.join('\n\n'));
      toast.success(t('workspace.codeExported'));
    } catch {
      toast.error(t('workspace.codeExportFailed'));
    }
  };

  const closeDeleteDialog = () => {
    setIsDeleteDialogOpen(false);
    setSessionToDelete(null);
  };

  return {
    messages,
    input,
    setInput,
    uploadedImages,
    setUploadedImages,
    isGenerating,
    sessions,
    isLoadingSessions,
    isDeleteDialogOpen,
    closeDeleteDialog,
    handleNewSession,
    handleDeleteSession,
    confirmDeleteSession,
    handleSelectSession,
    handleSendMessage,
    handleStopGeneration,
    handleAddFile,
    handleExportCode,
    handleRetryStreamRecovery,
  };
}
