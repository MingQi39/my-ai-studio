import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import type { ChatToolsState } from '@/components/ControlPanel';
import {
  createStudioAssistantPlaceholder,
  useStudioChatStream,
} from '@/hooks/useStudioChatStream';
import type { StudioChatMessage } from '@/hooks/studioChat/types';
import {
  createSession,
  deleteSession as apiDeleteSession,
  getSessionMessages,
  listSessions,
  updateSession,
  uploadFile,
  type ChatRequest,
  type MessageResponse as ApiMessageResponse,
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
        const localMessages: StudioChatMessage[] = apiMessages.map((msg: ApiMessageResponse) => ({
          id: msg.id,
          role: msg.role as 'user' | 'assistant',
          content: msg.content,
          thinking: msg.thinking_content || undefined,
          isThinking: false,
          images:
            msg.attachments && msg.attachments.length > 0
              ? msg.attachments.map((att: { id: string; url: string; name: string }) => ({
                  id: att.id,
                  url: att.url,
                  name: att.name,
                }))
              : undefined,
        }));
        setMessages(localMessages.reverse());
        setIsFirstMessage(localMessages.length === 0);
      } catch (error) {
        console.error('Failed to load messages:', error);
        toast.error(t('workspace.loadMessagesFailed'));
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

  useEffect(() => {
    if (currentSessionId) {
      if (skipLoadMessagesRef.current) {
        skipLoadMessagesRef.current = false;
      } else {
        loadSessionMessages(currentSessionId);
      }
    } else {
      setMessages([]);
      setIsFirstMessage(true);
    }
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
  };
}
