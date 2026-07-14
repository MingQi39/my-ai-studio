import React, { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Menu,
  Code2,
  Image as ImageIcon,
  FileText,
  X,
  Video,
  Loader2,
  StopCircle,
  Plus,
  MessageSquarePlus,
  Settings2,
  ArrowUp,
  LayoutGrid,
  Globe,
  Code,
  Terminal,
  FileJson,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { EllipsisTooltip } from "@/components/EllipsisTooltip";
import { cn } from "@/components/ui/utils";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EllipsisTooltip } from "@/components/EllipsisTooltip";
import {
  ChatEmptyState,
  ChatInputArea,
  ChatJumpToBottom,
  MessageQueuePanel,
  StudioChatMessageList,
  StudioLaunchpad,
} from "@/components/chat";
import { ToolToggle, type ChatToolsState, CHAT_TOOLS_AVAILABLE } from "@/components/ControlPanel";
import { ActiveModelBadge } from "@/components/ActiveModelBadge";
import { useChatAutoScroll } from "@/hooks/useChatAutoScroll";
import { useMessageQueue } from "@/hooks/useMessageQueue";
import { useStudioChat, type UploadedStudioImage } from "@/hooks/useStudioChat";

interface MainWorkspaceProps {
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
  isDarkMode: boolean;
  hasModelConfig: boolean | null;
  onOpenConnectionModal: (selectedProviderId?: string) => void;
  enableReasoning: boolean;
  currentSessionId: string | null;
  onSessionChange: (sessionId: string | null) => void;
  sessionRefreshTrigger?: number;
  onSessionsChange?: () => void;
  systemPrompt?: string;
  modelConfigId?: string | null;
  isControlPanelOpen?: boolean;
  toggleControlPanel?: () => void;
  onSelectProviderModel: (providerId: string, displayName: string) => void;
  selectedModel: string;
  hidden?: boolean;
  toolsState: ChatToolsState;
  onToolsStateChange: (state: ChatToolsState) => void;
}

export function MainWorkspace({
  isSidebarOpen,
  toggleSidebar,
  isDarkMode,
  hasModelConfig,
  onOpenConnectionModal,
  enableReasoning,
  currentSessionId,
  onSessionChange,
  sessionRefreshTrigger,
  onSessionsChange,
  systemPrompt,
  modelConfigId,
  isControlPanelOpen = true,
  toggleControlPanel,
  onSelectProviderModel,
  selectedModel,
  hidden = false,
  toolsState,
  onToolsStateChange,
}: MainWorkspaceProps) {
  if (hidden) return null;

  type StudioQueuePayload = {
    text: string;
    images: UploadedStudioImage[];
  };

  const { t } = useTranslation();
  const [isPlusMenuOpen, setIsPlusMenuOpen] = useState(false);
  const [isToolsMenuOpen, setIsToolsMenuOpen] = useState(false);

  const menuRef = useRef<HTMLDivElement>(null);
  const toolsMenuRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const {
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
  } = useStudioChat({
    currentSessionId,
    onSessionChange,
    sessionRefreshTrigger,
    onSessionsChange,
    hasModelConfig,
    onOpenConnectionModal: () => onOpenConnectionModal(),
    enableReasoning,
    systemPrompt,
    modelConfigId,
    toolsState,
  });

  const { queue, submit, remove, reorder } = useMessageQueue<StudioQueuePayload>({
    isBusy: isGenerating,
    send: async (payload) => {
      await handleSendMessage({
        content: payload.text,
        images: payload.images,
      });
    },
  });

  const handleSubmitMessage = () => {
    const text = input.trim();
    if (!text && uploadedImages.length === 0) return;

    const payload: StudioQueuePayload = {
      text,
      images: [...uploadedImages],
    };

    void submit(payload).then((result) => {
      if (result === "sent" || result === "queued") {
        setInput("");
        setUploadedImages([]);
      }
    });
  };

  const { scrollContainerRef, scrollSentinelRef, showJumpButton, scrollToBottom } = useChatAutoScroll({
    deps: [messages, isGenerating],
    active: messages.length > 0,
    resetKey: currentSessionId,
  });

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsPlusMenuOpen(false);
      }
      if (toolsMenuRef.current && !toolsMenuRef.current.contains(event.target as Node)) {
        setIsToolsMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  return (
    <div className="flex-1 flex flex-col h-full bg-[var(--bg-main)] min-w-0 font-sans transition-colors duration-300">
      <div className="h-[56px] sm:h-[60px] flex items-center justify-between gap-2 px-2 sm:px-4 border-b border-[var(--border-color)] flex-shrink-0 z-10 bg-[var(--bg-main)]">
        <div className="flex items-center gap-1 sm:gap-2 shrink-0">
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            className={`text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] rounded-md transition-transform ${!isSidebarOpen ? "rotate-180" : ""}`}
          >
            <Menu size={20} />
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={handleNewSession}
            className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] rounded-md flex items-center gap-2 px-2 sm:px-3"
          >
            <MessageSquarePlus size={18} />
            <span className="hidden sm:inline text-sm">{t("workspace.newChat")}</span>
          </Button>
        </div>

        <div className="flex-1 text-center min-w-0 px-1">
          {currentSessionId &&
            sessions.length > 0 &&
            (() => {
              const currentSession = sessions.find((session) => session.id === currentSessionId);
              return currentSession ? (
                <EllipsisTooltip className="inline-block max-w-full text-sm font-medium text-[var(--text-primary)] sm:max-w-[400px]">
                  {currentSession.title || t("workspace.untitledSession")}
                </EllipsisTooltip>
              ) : null;
            })()}
        </div>

        <div className="flex items-center gap-1 sm:gap-2 shrink-0">
          <ActiveModelBadge
            model={selectedModel}
            onClick={() => onOpenConnectionModal()}
            className="hidden md:inline-flex"
          />
          <Button
            variant="ghost"
            size="icon"
            onClick={handleExportCode}
            title={t("workspace.exportCode")}
            className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] rounded-md hidden sm:inline-flex"
          >
            <Code2 size={20} />
          </Button>
          {toggleControlPanel && (
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleControlPanel}
              className={`text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] rounded-md ${isControlPanelOpen ? "md:hidden" : ""}`}
            >
              <Settings2 size={20} />
            </Button>
          )}
        </div>
      </div>

      <div className="flex-1 flex flex-col min-h-0 relative">
        <div ref={scrollContainerRef} className="flex-1 overflow-y-auto min-h-0 custom-scrollbar">
          {messages.length === 0 && !currentSessionId ? (
            <StudioLaunchpad
              sessions={sessions}
              onSelectSession={handleSelectSession}
              onDeleteSession={handleDeleteSession}
              isLoadingSessions={isLoadingSessions}
              onOpenConnectionModal={onOpenConnectionModal}
              onSelectProviderModel={onSelectProviderModel}
            />
          ) : messages.length === 0 && currentSessionId ? (
            <ChatEmptyState
              variant="studio"
              logoAlt={t("common.appName")}
              title={t("workspace.startTalking")}
              subtitle={t("workspace.promptHint")}
            />
          ) : (
            <StudioChatMessageList
              messages={messages}
              isDarkMode={isDarkMode}
              scrollSentinelRef={scrollSentinelRef}
              onRecoveryRetry={handleRetryStreamRecovery}
              isRecoveryRetrying={isGenerating}
            />
          )}
        </div>

        {showJumpButton && messages.length > 0 && <ChatJumpToBottom onClick={() => scrollToBottom("smooth")} />}

        <div className="flex-shrink-0 w-full bg-[var(--bg-main)] px-3 sm:px-4 py-3 sm:py-4 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
          <div className="w-full max-w-[800px] mx-auto space-y-2">
            <MessageQueuePanel
              queue={queue}
              getLabel={(payload) =>
                payload.text ||
                t("workspace.imageDialog", { defaultValue: "图片对话" }) +
                  (payload.images.length > 0 ? ` (${payload.images.length})` : "")
              }
              onRemove={remove}
              onReorder={reorder}
              onEdit={(_id, payload) => {
                remove(_id);
                setInput(payload.text);
                setUploadedImages(payload.images);
              }}
            />
            <div
              className={cn(
                "relative rounded-2xl sm:rounded-[28px] p-2 flex flex-col gap-1 border transition-all duration-300 focus-within:ring-1 focus-within:ring-[var(--border-hover)]",
              )}
              style={{
                backgroundColor: "var(--bg-card)",
                borderColor: "var(--border-color)",
                boxShadow: isDarkMode
                  ? "0 25px 50px -12px rgba(0, 0, 0, 0.5)"
                  : "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
              }}
            >
              <ChatInputArea
                layout="studio"
                value={input}
                onChange={setInput}
                onSubmit={handleSubmitMessage}
                canSubmit={!!input.trim() || uploadedImages.length > 0}
                placeholder={
                  isGenerating ? t("chat.queue.followUpPlaceholder") : t("workspace.promptPlaceholder")
                }
                textareaRef={textareaRef}
                textareaMaxHeight="200px"
                prefix={
                  uploadedImages.length > 0 ? (
                    <div className="flex flex-wrap gap-2 px-3 pt-2">
                      {uploadedImages.map((image, index) => (
                        <div key={image.id} className="relative group animate-in zoom-in duration-200">
                          <div className="w-20 h-20 rounded-lg overflow-hidden border border-[var(--border-color)] bg-[var(--bg-hover)]">
                            <img src={image.url} alt={image.name} className="w-full h-full object-cover" />
                            {image.uploading && (
                              <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                                <Loader2 size={16} className="animate-spin text-white" />
                              </div>
                            )}
                          </div>
                          {!image.uploading && (
                            <button
                              type="button"
                              onClick={() =>
                                setUploadedImages(uploadedImages.filter((_, imageIndex) => imageIndex !== index))
                              }
                              className="absolute -top-1 -right-1 p-0.5 rounded-full bg-red-500 hover:bg-red-600 text-white transition-colors shadow-lg"
                            >
                              <X size={12} />
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : undefined
                }
                footer={
                  <div className="flex items-center justify-between px-2 pb-1 gap-2 flex-wrap">
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <ActiveModelBadge
                        model={selectedModel}
                        onClick={() => onOpenConnectionModal()}
                        variant="compact"
                      />
                      <div ref={toolsMenuRef} className="relative">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setIsPlusMenuOpen(false);
                            setIsToolsMenuOpen(!isToolsMenuOpen);
                          }}
                          className={`h-8 rounded-full px-3 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] flex items-center gap-2 text-xs font-medium ${isToolsMenuOpen ? "bg-[var(--bg-hover)] text-[var(--text-primary)]" : ""}`}
                        >
                          <LayoutGrid size={16} />
                          {t("workspace.tools")}
                        </Button>

                        {isToolsMenuOpen && (
                          <div className="absolute bottom-full left-0 mb-3 w-[min(16rem,calc(100vw-2rem))] bg-[var(--bg-card)] border border-[var(--border-color)] shadow-2xl rounded-xl overflow-hidden p-3 animate-in fade-in zoom-in-95 duration-200 z-50">
                            <div className="text-[10px] font-semibold text-[var(--text-secondary)] px-1 pb-2 uppercase tracking-wider">
                              {t("controlPanel.tools")}
                            </div>
                            <div className="flex flex-col gap-3">
                              <ToolToggle
                                icon={<Globe size={16} />}
                                label={t("controlPanel.googleSearch")}
                                checked={toolsState.search}
                                disabled={!CHAT_TOOLS_AVAILABLE}
                                onCheckedChange={(checked) =>
                                  onToolsStateChange({ ...toolsState, search: checked })
                                }
                              />
                              <ToolToggle
                                icon={<Terminal size={16} />}
                                label={t("controlPanel.codeExec")}
                                checked={toolsState.code}
                                disabled={!CHAT_TOOLS_AVAILABLE}
                                onCheckedChange={(checked) => onToolsStateChange({ ...toolsState, code: checked })}
                              />
                              <ToolToggle
                                icon={<Code size={16} />}
                                label={t("controlPanel.functionCall")}
                                checked={toolsState.function}
                                disabled={!CHAT_TOOLS_AVAILABLE}
                                onCheckedChange={(checked) =>
                                  onToolsStateChange({ ...toolsState, function: checked })
                                }
                              />
                              <ToolToggle
                                icon={<FileJson size={16} />}
                                label={t("controlPanel.structuredOutput")}
                                checked={toolsState.structured}
                                disabled={!CHAT_TOOLS_AVAILABLE}
                                onCheckedChange={(checked) =>
                                  onToolsStateChange({ ...toolsState, structured: checked })
                                }
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 relative">
                      <div ref={menuRef} className="relative">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            setIsToolsMenuOpen(false);
                            setIsPlusMenuOpen(!isPlusMenuOpen);
                          }}
                          className={`h-8 w-8 rounded-full text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] ${isPlusMenuOpen ? "bg-[var(--bg-hover)] text-[var(--text-primary)]" : ""}`}
                        >
                          <Plus size={20} />
                        </Button>

                        {isPlusMenuOpen && (
                          <div className="absolute bottom-full right-0 mb-3 w-[min(14rem,calc(100vw-2rem))] bg-[var(--bg-card)] border border-[var(--border-color)] shadow-2xl rounded-xl overflow-hidden p-1.5 animate-in fade-in zoom-in-95 duration-200 z-50">
                            <div className="text-[10px] font-semibold text-[var(--text-secondary)] px-3 py-2 uppercase tracking-wider">
                              {t("workspace.addContent")}
                            </div>
                            <MenuItem
                              icon={<ImageIcon size={16} className="text-blue-400" />}
                              label={t("workspace.uploadImage")}
                              onClick={() => {
                                handleAddFile("image");
                                setIsPlusMenuOpen(false);
                              }}
                            />
                            <MenuItem
                              icon={<FileText size={16} className="text-green-400" />}
                              label={t("workspace.uploadFile")}
                              onClick={() => {
                                handleAddFile("file");
                                setIsPlusMenuOpen(false);
                              }}
                            />
                            <MenuItem
                              icon={<Video size={16} className="text-purple-400" />}
                              label={t("workspace.recordMedia")}
                              onClick={() => {
                                handleAddFile("video");
                                setIsPlusMenuOpen(false);
                              }}
                            />
                          </div>
                        )}
                      </div>

                      <Button
                        type="button"
                        onClick={isGenerating ? handleStopGeneration : handleSubmitMessage}
                        disabled={!isGenerating && !input.trim() && uploadedImages.length === 0}
                        aria-label={isGenerating ? t("workspace.stopGenerate") : t("workspace.send")}
                        className={cn(
                          "group relative h-8 w-8 p-0 rounded-full border-0 shadow-none flex items-center justify-center text-white transition-[background,box-shadow,transform] duration-150 active:scale-95",
                          "disabled:opacity-100 disabled:cursor-not-allowed",
                          isGenerating
                            ? "bg-red-500 hover:bg-red-600"
                            : [
                                "bg-[linear-gradient(180deg,#4782FF_0%,#3572FF_100%)]",
                                "hover:bg-[linear-gradient(180deg,#3474F5_0%,#084FDD_100%)] hover:shadow-[0_4px_12px_-2px_rgba(8,79,221,0.45)]",
                                "disabled:bg-none disabled:bg-[#165DFF] disabled:opacity-50 disabled:shadow-none",
                              ],
                        )}
                      >
                        {isGenerating ? (
                          <StopCircle size={16} className="fill-current" />
                        ) : (
                          <ArrowUp size={16} strokeWidth={2.25} />
                        )}
                      </Button>
                    </div>
                  </div>
                }
              />
            </div>
          </div>
        </div>
      </div>

      <ConfirmDialog
        isOpen={isDeleteDialogOpen}
        onClose={closeDeleteDialog}
        onConfirm={confirmDeleteSession}
        title={t("sidebar.deleteSessionTitle")}
        message={t("sidebar.deleteSessionMessage")}
        confirmText={t("common.delete")}
        cancelText={t("common.cancel")}
        isDarkMode={isDarkMode}
        type="danger"
      />
    </div>
  );
}

function MenuItem({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors text-sm text-left group"
    >
      {icon}
      <span className="group-hover:text-[var(--text-primary)] transition-colors">{label}</span>
    </button>
  );
}
