import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Menu, Code2, Sparkles, Image as ImageIcon, FileText, X, ChevronDown, Video, Terminal, Loader2, StopCircle, Plus, Bot, Zap, Copy, ExternalLink, MessageSquarePlus, Trash2, Cloud, Settings2, ArrowUp, LayoutGrid, Globe, Code, FileJson } from 'lucide-react';
import { MessageContent } from '@/components/MessageContent';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/components/ui/utils';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import {
   SessionResponse,
   MessageResponse as ApiMessageResponse,
   ChatStreamChunk,
   createSession,
   listSessions,
   updateSession,
   deleteSession as apiDeleteSession,
   getSessionMessages,
   streamChat,
   ChatRequest,
   uploadFile,
   FileUploadResponse,
   listModelConfigs,
   ModelConfigResponse,
} from '@/services/api';

import { BrandLogo } from '@/components/BrandLogo';
import { ToolToggle, type ChatToolsState, CHAT_TOOLS_AVAILABLE } from '@/components/ControlPanel';
import { ActiveModelBadge } from '@/components/ActiveModelBadge';

// Types for our Messages
type ChatToolRun = {
   tool_name: string;
   tool_type?: string;
   tool_input?: Record<string, unknown>;
   tool_output?: string;
   status: 'running' | 'completed' | 'error';
};

type Message = {
   id: string;
   role: 'user' | 'assistant';
   content: string;
   images?: Array<{
      id: string;
      url: string;
      name: string;
   }>;
   thinking?: string;
   isThinking?: boolean;
   tool?: {
      name: string;
      code: string;
      output?: string;
      status: 'running' | 'completed';
   };
   toolRuns?: ChatToolRun[];
};

interface MainWorkspaceProps {
   isSidebarOpen: boolean;
   toggleSidebar: () => void;
   isDarkMode: boolean;
   hasModelConfig: boolean | null; // null = Loading, false = No config, true = Has config
   onOpenConnectionModal: (selectedProviderId?: string) => void;
   enableReasoning: boolean;
   currentSessionId: string | null;
   onSessionChange: (sessionId: string | null) => void;
   sessionRefreshTrigger?: number;
   onSessionsChange?: () => void;
   systemPrompt?: string; // system prompt
   modelConfigId?: string | null; // currently selected model config ID
   isControlPanelOpen?: boolean; // whether the right control panel is expanded
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
   currentSessionId: externalSessionId,
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
   const { t, i18n } = useTranslation();
   const [input, setInput] = useState('');
   const [uploadedImages, setUploadedImages] = useState<Array<{
      id: string;
      url: string;
      name: string;
      file: File;
      uploading?: boolean;
   }>>([]);
   const [messages, setMessages] = useState<Message[]>([]);
   const [isGenerating, setIsGenerating] = useState(false);
   const [isPlusMenuOpen, setIsPlusMenuOpen] = useState(false);
   const [isToolsMenuOpen, setIsToolsMenuOpen] = useState(false);

   // Session State
   const [sessions, setSessions] = useState<SessionResponse[]>([]);
   const [isLoadingSessions, setIsLoadingSessions] = useState(true);
   const [isFirstMessage, setIsFirstMessage] = useState(true);

   // confirm dialog state
   const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
   const [sessionToDelete, setSessionToDelete] = useState<string | null>(null);

   // use externally-provided currentSessionId
   const currentSessionId = externalSessionId;
   const setCurrentSessionId = onSessionChange;

   const abortControllerRef = useRef<AbortController | null>(null);
   const skipLoadMessagesRef = useRef(false);

   const scrollRef = useRef<HTMLDivElement>(null);
   const menuRef = useRef<HTMLDivElement>(null);
   const toolsMenuRef = useRef<HTMLDivElement>(null);
   const textareaRef = useRef<HTMLTextAreaElement>(null);

   // Load Sessions
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
   }, []);

   // Load Session Messages
   const loadSessionMessages = useCallback(async (sessionId: string) => {
      try {
         const apiMessages = await getSessionMessages(sessionId, 100);
         // Convert API messages to local format
         const localMessages: Message[] = apiMessages.map((msg: ApiMessageResponse) => ({
            id: msg.id,
            role: msg.role as 'user' | 'assistant',
            content: msg.content,
            thinking: msg.thinking_content || undefined,
            isThinking: false,
            // convert attachments to images
            images: msg.attachments && msg.attachments.length > 0
               ? msg.attachments.map((att: any) => ({
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
   }, []);

   // Initial load
   useEffect(() => {
      loadSessions();
   }, [loadSessions]);

   // listen for session refresh trigger (when sidebar deletes a session)
   useEffect(() => {
      if (sessionRefreshTrigger !== undefined && sessionRefreshTrigger > 0) {
         loadSessions();
      }
   }, [sessionRefreshTrigger, loadSessions]);

   // Load messages when session changes
   useEffect(() => {
      if (currentSessionId) {
         if (skipLoadMessagesRef.current) {
            // when creating a new session from sending a homepage message, do not clear messages
            // messages have already been added in handleSendMessage
            skipLoadMessagesRef.current = false;
            // do not setMessages([]), keep current messages
         } else {
            loadSessionMessages(currentSessionId);
         }
      } else {
         setMessages([]);
         setIsFirstMessage(true);
      }
   }, [currentSessionId, loadSessionMessages]);


   // Auto-scroll
   useEffect(() => {
      if (scrollRef.current) {
         scrollRef.current.scrollIntoView({ behavior: 'smooth' });
      }
   }, [messages, isGenerating]);

   // Click outside menus
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

   // Create New Session
   const handleNewSession = async () => {
      try {
         const session = await createSession({
            title: t('workspace.newChat')
         });
         setSessions(prev => [session, ...prev]);
         skipLoadMessagesRef.current = true;
         setCurrentSessionId(session.id);
         setMessages([]);
         setIsFirstMessage(true);
         toast.success(t('workspace.newChatCreated'));
         onSessionsChange?.();
      } catch (error) {
         console.error('Failed to create session:', error);
         toast.error(t('workspace.newChatFailed'));
      }
   };

   // Delete Session
   const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
      e.stopPropagation();
      setSessionToDelete(sessionId);
      setIsDeleteDialogOpen(true);
   };

   const confirmDeleteSession = async () => {
      if (!sessionToDelete) return;
      try {
         await apiDeleteSession(sessionToDelete);
         setSessions(prev => prev.filter(s => s.id !== sessionToDelete));
         if (currentSessionId === sessionToDelete) {
            setCurrentSessionId(null);
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

   // Select Session
   const handleSelectSession = (sessionId: string) => {
      setCurrentSessionId(sessionId);
   };

   const handleSendMessage = async () => {
      if (!input.trim() && uploadedImages.length === 0) return;

      // Check model config
      if (hasModelConfig === false) {
         toast.error(t('workspace.needModelConfig'));
         onOpenConnectionModal();
         return;
      }

      if (hasModelConfig === null) {
         toast.info(t('workspace.loadingConfig'));
         return;
      }

      // check if any image is still uploading
      if (uploadedImages.some(img => img.uploading)) {
         toast.info(t('workspace.waitingUpload'));
         return;
      }

      const messageContent = input.trim();
      let sessionId = currentSessionId;

      // Create session if none exists
      if (!sessionId) {
         try {
            const title = messageContent.length > 20
               ? messageContent.substring(0, 20) + '...'
               : messageContent || t('workspace.imageDialog');
            const session = await createSession({ title });
            setSessions(prev => [session, ...prev]);
            sessionId = session.id;
            skipLoadMessagesRef.current = true;
            setCurrentSessionId(sessionId);
         } catch (error) {
            console.error('Failed to create session:', error);
            toast.error(t('workspace.createSessionFailed'));
            return;
         }
      } else if (isFirstMessage && messageContent) {
         // Update title if first message
         try {
            const title = messageContent.length > 20
               ? messageContent.substring(0, 20) + '...'
               : messageContent;
            await updateSession(sessionId, { title });
            setSessions(prev => prev.map(s =>
               s.id === sessionId ? { ...s, title } : s
            ));
            onSessionsChange?.();
         } catch (error) {
            console.error('Failed to update session title:', error);
         }
      }

      // 1. Add User Message (with images)
      const userMsg: Message = {
         id: Date.now().toString(),
         role: 'user',
         content: messageContent,
         images: uploadedImages.length > 0 ? uploadedImages.map(img => ({
            id: img.id,
            url: img.url,
            name: img.name,
         })) : undefined,
      };

      setMessages(prev => [...prev, userMsg]);
      setInput('');
      const currentImages = [...uploadedImages];
      setUploadedImages([]); // clear image list
      setIsGenerating(true);
      setIsFirstMessage(false);

      // 2. Placeholder Assistant Message
      const aiMsgId = (Date.now() + 1).toString();
      setMessages(prev => [...prev, {
         id: aiMsgId,
         role: 'assistant',
         content: '',
         isThinking: true,
         thinking: '',
      }]);

      // 3. Call API
      const chatRequest: ChatRequest = {
         session_id: sessionId,
         message: messageContent,
         file_ids: currentImages.length > 0 ? currentImages.map(img => img.id) : undefined,
         stream: true,
         enable_reasoning: enableReasoning,
         system_prompt: systemPrompt || undefined,
         model_config_id: modelConfigId || undefined,
         tools_config: toolsState,
      };

      let thinkingContent = '';
      let responseContent = '';

      await streamChat(
         chatRequest,
         (chunk: ChatStreamChunk) => {
            if (chunk.type === 'thinking') {
               thinkingContent += chunk.thinking || '';
               setMessages(prev => prev.map(m =>
                  m.id === aiMsgId
                     ? { ...m, thinking: thinkingContent, isThinking: true }
                     : m
               ));
            } else if (chunk.type === 'content') {
               responseContent += chunk.content || '';
               setMessages(prev => prev.map(m =>
                  m.id === aiMsgId
                     ? { ...m, content: responseContent, isThinking: true }
                     : m
               ));
            } else if (chunk.type === 'tool_result' && chunk.tool_result) {
               const tr = chunk.tool_result;
               setMessages(prev => prev.map(m => {
                  if (m.id !== aiMsgId) return m;
                  const runs = [...(m.toolRuns || [])];
                  const runningIdx = runs.findIndex(
                     r => r.tool_name === tr.tool_name && r.status === 'running'
                  );
                  if (tr.status === 'running') {
                     runs.push({ ...tr });
                  } else if (runningIdx >= 0) {
                     runs[runningIdx] = { ...runs[runningIdx], ...tr };
                  } else {
                     runs.push({ ...tr });
                  }

                  let tool = m.tool;
                  if (tr.tool_name === 'execute_python') {
                     const code = String(tr.tool_input?.code ?? '');
                     if (tr.status === 'running') {
                        tool = { name: tr.tool_name, code, status: 'running' };
                     } else {
                        tool = {
                           name: tr.tool_name,
                           code,
                           output: tr.tool_output,
                           status: tr.status === 'error' ? 'running' : 'completed',
                        };
                     }
                  }

                  return { ...m, toolRuns: runs, tool, isThinking: true };
               }));
            } else if (chunk.type === 'done') {
               setMessages(prev => prev.map(m =>
                  m.id === aiMsgId
                     ? { ...m, isThinking: false }
                     : m
               ));
            }
         },
         (error: Error) => {
            console.error('Chat error:', error);
            toast.error(t('workspace.chatError', { message: error.message }));
            setMessages(prev => prev.map(m =>
               m.id === aiMsgId
                  ? { ...m, content: t('workspace.errorPrefix', { message: error.message }), isThinking: false }
                  : m
            ));
            setIsGenerating(false);
         },
         () => {
            setIsGenerating(false);
            loadSessions();
            onSessionsChange?.();
         }
      );
   };

   const handleStopGeneration = () => {
      if (abortControllerRef.current) {
         abortControllerRef.current.abort();
      }
      setIsGenerating(false);
   };

   const handleAddFile = async (type: 'image' | 'file' | 'video') => {
      // create file input element
      const input = document.createElement('input');
      input.type = 'file';

      // set accepted formats according to type
      if (type === 'image') {
         input.accept = 'image/*';
      } else if (type === 'video') {
         input.accept = 'video/*,audio/*';
      } else {
         input.accept = '*/*';
      }

      input.onchange = async (e) => {
         const file = (e.target as HTMLInputElement).files?.[0];
         if (!file) return;

         // only process images (per requirements)
         if (type === 'image') {
            try {
               // add to preview list (showing uploading state)
               const tempId = `temp_${Date.now()}`;
               const tempUrl = URL.createObjectURL(file);
               setUploadedImages(prev => [...prev, {
                  id: tempId,
                  url: tempUrl,
                  name: file.name,
                  file,
                  uploading: true,
               }]);

               // upload the file
               const uploadedFile = await uploadFile(file);

               // update to uploaded state
               setUploadedImages(prev => prev.map(img =>
                  img.id === tempId
                     ? { ...img, id: uploadedFile.id, url: uploadedFile.url, uploading: false }
                     : img
               ));

               toast.success(t('workspace.imageUploaded'));
            } catch (error) {
               console.error('Upload failed:', error);
               toast.error(t('workspace.imageUploadFailed'));
               // remove failed images
               setUploadedImages(prev => prev.filter(img => !img.uploading));
            }
         } else {
            toast.info(t('workspace.unsupportedFile'));
         }
      };

      input.click();
      setIsPlusMenuOpen(false);
   };

   const handleExportCode = async () => {
      const snippets: string[] = [];

      for (const msg of messages) {
         if (msg.tool?.code?.trim()) {
            snippets.push(msg.tool.code.trim());
         }

         for (const run of msg.toolRuns ?? []) {
            if (run.tool_name === 'execute_python') {
               const code = String(run.tool_input?.code ?? '').trim();
               if (code) snippets.push(code);
            }
         }

         if (msg.content) {
            const fenced = msg.content.matchAll(/```(?:[\w+-]*)?\n([\s\S]*?)```/g);
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


   return (
      <div className="flex-1 flex flex-col h-full bg-[var(--bg-main)] min-w-0 font-sans transition-colors duration-300">
         {/* 1. Header Area - Fixed height */}
         <div className="h-[60px] flex items-center justify-between px-4 border-b border-[var(--border-color)] flex-shrink-0 z-10 bg-[var(--bg-main)]">
            <div className="flex items-center gap-2">
               <Button
                  variant="ghost"
                  size="icon"
                  onClick={toggleSidebar}
                  className={`text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] rounded-md transition-transform ${!isSidebarOpen ? 'rotate-180' : ''}`}
               >
                  <Menu size={20} />
               </Button>

               {/* New Chat Button */}
               <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleNewSession}
                  className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] rounded-md flex items-center gap-2"
               >
                  <MessageSquarePlus size={18} />
                  <span className="hidden sm:inline text-sm">{t('workspace.newChat')}</span>
               </Button>
            </div>

            <div className="flex-1 text-center">
               {currentSessionId && sessions.length > 0 && (() => {
                  const currentSession = sessions.find(s => s.id === currentSessionId);
                  return currentSession ? (
                     <span className="text-sm font-medium text-[var(--text-primary)] truncate max-w-[400px] inline-block">
                        {currentSession.title || t('workspace.untitledSession')}
                     </span>
                  ) : null;
               })()}
            </div>
            <div className="flex items-center gap-2">
               <ActiveModelBadge
                  model={selectedModel}
                  onClick={() => onOpenConnectionModal()}
                  className="hidden md:inline-flex"
               />
               <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleExportCode}
                  title={t('workspace.exportCode')}
                  className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] rounded-md"
               >
                  <Code2 size={20} />
               </Button>
               {/* only show the expand button when the control panel is collapsed */}
               {toggleControlPanel && !isControlPanelOpen && (
                  <Button
                     variant="ghost"
                     size="icon"
                     onClick={toggleControlPanel}
                     className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] rounded-md"
                  >
                     <Settings2 size={20} />
                  </Button>
               )}
            </div>
         </div>

         {/* 2. Chat History Area - Flex grow with scroll */}
         <div className="flex-1 overflow-y-auto min-h-0 custom-scrollbar">
            {messages.length === 0 && !currentSessionId ? (
               <Launchpad
                  sessions={sessions}
                  onSelectSession={handleSelectSession}
                  onDeleteSession={handleDeleteSession}
                  isLoadingSessions={isLoadingSessions}
                  onOpenConnectionModal={onOpenConnectionModal}
                  onSelectProviderModel={onSelectProviderModel}
               />
            ) : messages.length === 0 && currentSessionId ? (
               <div className="w-full max-w-[850px] mx-auto flex flex-col items-center justify-center pt-[20vh] px-6">
                  <div className="text-center">
                     <BrandLogo size="lg" className="mx-auto mb-4 opacity-90" alt={t('common.appName')} />
                     <p className="text-lg text-[var(--text-secondary)]">{t('workspace.startTalking')}</p>
                     <p className="text-sm text-[var(--text-placeholder)] mt-2">{t('workspace.promptHint')}</p>
                  </div>
               </div>
            ) : (
               <div className="max-w-[900px] mx-auto py-10 px-6 flex flex-col gap-10">
                  {messages.map((msg) => (
                     <div key={msg.id} className="flex flex-col gap-6 animate-in fade-in duration-500 slide-in-from-bottom-2">
                        {msg.role === 'user' ? (
                           <div className="flex gap-4 justify-end">
                              <div className="bg-[var(--bg-card)] text-[var(--text-primary)] px-4 py-3 rounded-2xl rounded-tr-sm max-w-[80%] leading-relaxed border border-[var(--border-color)]">
                                 {/* images */}
                                 {msg.images && msg.images.length > 0 && (
                                    <div className="flex flex-wrap gap-2 mb-2">
                                       {msg.images.map((image) => (
                                          <div key={image.id} className="rounded-lg overflow-hidden border border-[var(--border-color)] cursor-pointer hover:opacity-80 transition-opacity">
                                             <img
                                                src={image.url}
                                                alt={image.name}
                                                className="max-w-[200px] max-h-[200px] object-cover"
                                                onClick={() => window.open(image.url, '_blank')}
                                             />
                                          </div>
                                       ))}
                                    </div>
                                 )}
                                 {/* text */}
                                 {msg.content && <p className="whitespace-pre-wrap">{msg.content}</p>}
                              </div>
                           </div>
                        ) : (
                           <div className="flex flex-col gap-6">
                              {/* Thinking Block */}
                              {msg.thinking && (
                                 <ThinkingBlock
                                    text={msg.thinking}
                                    isStreaming={msg.isThinking}
                                    isDarkMode={isDarkMode}
                                 />
                              )}

                              {/* Tool runs (search / function) */}
                              {msg.toolRuns && msg.toolRuns.filter(r => r.tool_name !== 'execute_python').map((run, i) => (
                                 <ChatToolRunBlock key={`${run.tool_name}-${i}`} run={run} isDarkMode={isDarkMode} />
                              ))}

                              {/* Python execution block */}
                              {msg.tool && (
                                 <ToolExecutionBlock
                                    code={msg.tool.code}
                                    output={msg.tool.output}
                                    status={msg.tool.status}
                                    isDarkMode={isDarkMode}
                                 />
                              )}

                              {/* Final Content */}
                              {msg.content && (
                                 <MessageContent
                                    content={msg.content}
                                    isStreaming={msg.isThinking}
                                    isDarkMode={isDarkMode}
                                 />
                              )}

                              {/* Loading indicator */}
                              {!msg.content && msg.isThinking && !msg.thinking && (
                                 <div className="flex items-center gap-2 text-[var(--text-secondary)]">
                                    <Loader2 size={16} className="animate-spin" />
                                    <span className="text-sm">{t('workspace.thinking')}</span>
                                 </div>
                              )}
                           </div>
                        )}
                     </div>
                  ))}

                  {/* Scroll Anchor */}
                  <div ref={scrollRef} />
               </div>
            )}
         </div>

         {/* 3. Input Area - Natural flow at bottom */}
         <div className="flex-shrink-0 w-full bg-[var(--bg-main)] px-4 py-4">
            <div className="w-[800px] max-w-full mx-auto">
               <div
                  className={`
             relative rounded-[28px] p-2 flex flex-col gap-1 border transition-all duration-300
             ${isGenerating ? 'opacity-50 pointer-events-none grayscale' : 'focus-within:ring-1 focus-within:ring-[var(--border-hover)]'}
           `}
                  style={{
                     backgroundColor: 'var(--bg-card)',
                     borderColor: 'var(--border-color)',
                     boxShadow: isDarkMode ? '0 25px 50px -12px rgba(0, 0, 0, 0.5)' : '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
                  }}
               >

                  {/* Image Preview */}
                  {uploadedImages.length > 0 && (
                     <div className="flex flex-wrap gap-2 px-3 pt-2">
                        {uploadedImages.map((image, i) => (
                           <div key={image.id} className="relative group animate-in zoom-in duration-200">
                              <div className="w-20 h-20 rounded-lg overflow-hidden border border-[var(--border-color)] bg-[var(--bg-hover)]">
                                 <img
                                    src={image.url}
                                    alt={image.name}
                                    className="w-full h-full object-cover"
                                 />
                                 {image.uploading && (
                                    <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                                       <Loader2 size={16} className="animate-spin text-white" />
                                    </div>
                                 )}
                              </div>
                              {!image.uploading && (
                                 <button
                                    onClick={() => setUploadedImages(uploadedImages.filter((_, index) => index !== i))}
                                    className="absolute -top-1 -right-1 p-0.5 rounded-full bg-red-500 hover:bg-red-600 text-white transition-colors shadow-lg"
                                 >
                                    <X size={12} />
                                 </button>
                              )}
                           </div>
                        ))}
                     </div>
                  )}

                  <textarea
                     ref={textareaRef}
                     value={input}
                     onChange={(e) => setInput(e.target.value)}
                     onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                           e.preventDefault();
                           handleSendMessage();
                        }
                     }}
                     placeholder={t('workspace.promptPlaceholder')}
                     className="w-full bg-transparent border-none outline-none text-[var(--text-primary)] placeholder:text-[var(--text-placeholder)] resize-none min-h-[40px] px-4 py-2 text-base custom-scrollbar"
                     rows={1}
                     style={{ maxHeight: '200px' }}
                     disabled={isGenerating}
                  />

                  {/* Bottom Controls Row */}
                  <div className="flex items-center justify-between px-2 pb-1">

                     {/* Left Controls */}
                     <div className="flex items-center gap-2 min-w-0">
                        <ActiveModelBadge
                           model={selectedModel}
                           onClick={() => onOpenConnectionModal()}
                           variant="compact"
                           className="max-w-[180px] sm:max-w-[220px]"
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
                              className={`h-8 rounded-full px-3 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] flex items-center gap-2 text-xs font-medium ${isToolsMenuOpen ? 'bg-[var(--bg-hover)] text-[var(--text-primary)]' : ''}`}
                           >
                              <LayoutGrid size={16} />
                              {t('workspace.tools')}
                           </Button>

                           {isToolsMenuOpen && (
                              <div className="absolute bottom-full left-0 mb-3 w-64 bg-[var(--bg-card)] border border-[var(--border-color)] shadow-2xl rounded-xl overflow-hidden p-3 animate-in fade-in zoom-in-95 duration-200 z-50">
                                 <div className="text-[10px] font-semibold text-[var(--text-secondary)] px-1 pb-2 uppercase tracking-wider">
                                    {t('controlPanel.tools')}
                                 </div>
                                 <div className="flex flex-col gap-3">
                                    <ToolToggle
                                       icon={<Globe size={16} />}
                                       label={t('controlPanel.googleSearch')}
                                       checked={toolsState.search}
                                       disabled={!CHAT_TOOLS_AVAILABLE}
                                       onCheckedChange={(c) => onToolsStateChange({ ...toolsState, search: c })}
                                    />
                                    <ToolToggle
                                       icon={<Terminal size={16} />}
                                       label={t('controlPanel.codeExec')}
                                       checked={toolsState.code}
                                       disabled={!CHAT_TOOLS_AVAILABLE}
                                       onCheckedChange={(c) => onToolsStateChange({ ...toolsState, code: c })}
                                    />
                                    <ToolToggle
                                       icon={<Code size={16} />}
                                       label={t('controlPanel.functionCall')}
                                       checked={toolsState.function}
                                       disabled={!CHAT_TOOLS_AVAILABLE}
                                       onCheckedChange={(c) => onToolsStateChange({ ...toolsState, function: c })}
                                    />
                                    <ToolToggle
                                       icon={<FileJson size={16} />}
                                       label={t('controlPanel.structuredOutput')}
                                       checked={toolsState.structured}
                                       disabled={!CHAT_TOOLS_AVAILABLE}
                                       onCheckedChange={(c) => onToolsStateChange({ ...toolsState, structured: c })}
                                    />
                                 </div>
                              </div>
                           )}
                        </div>
                     </div>

                     {/* Right Controls */}
                     <div className="flex items-center gap-2 relative">

                        {/* Plus Menu Trigger */}
                        <div ref={menuRef} className="relative">
                           <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => {
                                 setIsToolsMenuOpen(false);
                                 setIsPlusMenuOpen(!isPlusMenuOpen);
                              }}
                              className={`h-8 w-8 rounded-full text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] ${isPlusMenuOpen ? 'bg-[var(--bg-hover)] text-[var(--text-primary)]' : ''}`}
                           >
                              <Plus size={20} />
                           </Button>

                           {/* Popover Menu */}
                           {isPlusMenuOpen && (
                              <div className="absolute bottom-full right-0 mb-3 w-56 bg-[var(--bg-card)] border border-[var(--border-color)] shadow-2xl rounded-xl overflow-hidden p-1.5 animate-in fade-in zoom-in-95 duration-200 z-50">
                                 <div className="text-[10px] font-semibold text-[var(--text-secondary)] px-3 py-2 uppercase tracking-wider">{t('workspace.addContent')}</div>
                                 <MenuItem
                                    icon={<ImageIcon size={16} className="text-blue-400" />}
                                    label={t('workspace.uploadImage')}
                                    onClick={() => handleAddFile('image')}
                                 />
                                 <MenuItem
                                    icon={<FileText size={16} className="text-green-400" />}
                                    label={t('workspace.uploadFile')}
                                    onClick={() => handleAddFile('file')}
                                 />
                                 <MenuItem
                                    icon={<Video size={16} className="text-purple-400" />}
                                    label={t('workspace.recordMedia')}
                                    onClick={() => handleAddFile('video')}
                                 />
                              </div>
                           )}
                        </div>

                        {/* Send Button — 1:1 to Figma node 12341:7250 / 12341:7258 / 12347:13339 */}
                        <Button
                           type="button"
                           onClick={isGenerating ? handleStopGeneration : handleSendMessage}
                           disabled={!isGenerating && (!input.trim() && uploadedImages.length === 0)}
                           aria-label={isGenerating ? t('workspace.stopGenerate') : t('workspace.send')}
                           className={cn(
                              'group relative h-8 w-8 p-0 rounded-full border-0 shadow-none flex items-center justify-center text-white transition-[background,box-shadow,transform] duration-150 active:scale-95',
                              'disabled:opacity-100 disabled:cursor-not-allowed',
                              isGenerating
                                 ? 'bg-red-500 hover:bg-red-600'
                                 : [
                                    // enabled (default): vertical gradient #4782FF → #3572FF (sampled 1:1 from Figma)
                                    'bg-[linear-gradient(180deg,#4782FF_0%,#3572FF_100%)]',
                                    // hover: deeper #3474F5 → #084FDD with soft lift
                                    'hover:bg-[linear-gradient(180deg,#3474F5_0%,#084FDD_100%)] hover:shadow-[0_4px_12px_-2px_rgba(8,79,221,0.45)]',
                                    // disabled: solid #165DFF at 50% opacity
                                    'disabled:bg-none disabled:bg-[#165DFF] disabled:opacity-50 disabled:shadow-none',
                                 ]
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

               </div>
            </div>
         </div>
         <ConfirmDialog
            isOpen={isDeleteDialogOpen}
            onClose={() => {
               setIsDeleteDialogOpen(false);
               setSessionToDelete(null);
            }}
            onConfirm={confirmDeleteSession}
            title={t('sidebar.deleteSessionTitle')}
            message={t('sidebar.deleteSessionMessage')}
            confirmText={t('common.delete')}
            cancelText={t('common.cancel')}
            isDarkMode={isDarkMode}
            type="danger"
         />
      </div>
   );
}

// ----------------------------------------------------------------------------------
// Sub-Components
// ----------------------------------------------------------------------------------

function MenuItem({ icon, label, onClick }: { icon: React.ReactNode, label: string, onClick: () => void }) {
   return (
      <button
         onClick={onClick}
         className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors text-sm text-left group"
      >
         {icon}
         <span className="group-hover:text-[var(--text-primary)] transition-colors">{label}</span>
      </button>
   )
}

type LaunchpadBadge = { textKey: string; color: 'blue' | 'green' | 'purple' | 'orange' | 'grey' };

type LaunchpadModelDef = {
   id: string;
   providerId: string;
   titleKey: string;
   descKey: string;
   icon: React.ReactNode;
   iconBg: string;
   badgeKeys: LaunchpadBadge[];
   categories: string[];
};

const LAUNCHPAD_MODELS: LaunchpadModelDef[] = [
   {
      id: 'deepseek',
      providerId: 'deepseek',
      titleKey: 'launchpad.models.deepseek.title',
      descKey: 'launchpad.models.deepseek.desc',
      icon: <Bot size={18} className="text-blue-500" />,
      iconBg: 'bg-blue-500/10',
      badgeKeys: [{ textKey: 'launchpad.badges.new', color: 'green' }, { textKey: 'launchpad.badges.opensource', color: 'grey' }],
      categories: ['all', 'text'],
   },
   {
      id: 'openai',
      providerId: 'openai',
      titleKey: 'launchpad.models.openai.title',
      descKey: 'launchpad.models.openai.desc',
      icon: <Zap size={18} className="text-emerald-500" />,
      iconBg: 'bg-emerald-500/10',
      badgeKeys: [{ textKey: 'launchpad.badges.paid', color: 'blue' }],
      categories: ['all', 'text'],
   },
   {
      id: 'gemini',
      providerId: 'gemini',
      titleKey: 'launchpad.models.gemini.title',
      descKey: 'launchpad.models.gemini.desc',
      icon: <Sparkles size={18} className="text-indigo-500" />,
      iconBg: 'bg-indigo-500/10',
      badgeKeys: [{ textKey: 'launchpad.badges.multimodal', color: 'purple' }],
      categories: ['all', 'multimodal'],
   },
   {
      id: 'qwen',
      providerId: 'qwen',
      titleKey: 'launchpad.models.qwen.title',
      descKey: 'launchpad.models.qwen.desc',
      icon: <Cloud size={18} className="text-purple-500" />,
      iconBg: 'bg-purple-500/10',
      badgeKeys: [{ textKey: 'launchpad.badges.localCapable', color: 'orange' }],
      categories: ['all', 'text', 'local'],
   },
   {
      id: 'openrouter',
      providerId: 'openrouter',
      titleKey: 'launchpad.models.openrouter.title',
      descKey: 'launchpad.models.openrouter.desc',
      icon: <ExternalLink size={18} className="text-green-500" />,
      iconBg: 'bg-green-500/10',
      badgeKeys: [{ textKey: 'launchpad.badges.aggregator', color: 'blue' }],
      categories: ['all', 'text'],
   },
   {
      id: 'ollama',
      providerId: 'ollama',
      titleKey: 'launchpad.models.ollama.title',
      descKey: 'launchpad.models.ollama.desc',
      icon: <Terminal size={18} className="text-orange-500" />,
      iconBg: 'bg-orange-500/10',
      badgeKeys: [{ textKey: 'launchpad.badges.local', color: 'orange' }],
      categories: ['all', 'local'],
   },
];

function configMatchesProvider(config: ModelConfigResponse, providerId: string): boolean {
   if (config.adapter_type === 'official' && config.provider === providerId) return true;
   return config.adapter_type === providerId;
}

function Launchpad({
   sessions,
   onSelectSession,
   onDeleteSession,
   isLoadingSessions,
   onOpenConnectionModal,
   onSelectProviderModel,
}: {
   isDarkMode: boolean;
   sessions: SessionResponse[];
   onSelectSession: (sessionId: string) => void;
   onDeleteSession: (sessionId: string, e: React.MouseEvent) => void;
   isLoadingSessions: boolean;
   onOpenConnectionModal: (selectedProviderId?: string) => void;
   onSelectProviderModel: (providerId: string, displayName: string) => void;
}) {
   const { t, i18n } = useTranslation();
   const [activeTab, setActiveTab] = useState('all');
   const [modelConfigs, setModelConfigs] = useState<ModelConfigResponse[]>([]);

   useEffect(() => {
      listModelConfigs()
         .then(setModelConfigs)
         .catch((err) => console.error('Failed to load model configs:', err));
   }, []);

   const isProviderConfigured = (providerId: string) =>
      modelConfigs.some((c) => configMatchesProvider(c, providerId));

   const filteredModels = LAUNCHPAD_MODELS.filter((m) => m.categories.includes(activeTab));

   const handleModelClick = (providerId: string, displayName: string) => {
      if (!isProviderConfigured(providerId)) {
         toast.info(t('launchpad.configureFirst', { name: displayName }));
         onOpenConnectionModal(providerId);
      } else {
         onSelectProviderModel(providerId, displayName);
      }
   };

   return (
      <div className="w-full max-w-[850px] mx-auto flex flex-col items-center pt-[5vh] px-6 pb-12">
         <div className="text-center flex flex-col items-center mb-8 gap-4">
            <div className="rounded-2xl shadow-sm overflow-hidden p-2">
               <BrandLogo size="xl" alt={t('common.appName')} />
            </div>
            <div className="flex flex-col gap-2">
               <h1 className="text-[24px] font-semibold text-[var(--text-primary)] tracking-tight">{t('launchpad.title')}</h1>
               <p className="text-[var(--text-secondary)] text-[14px] leading-relaxed max-w-[500px]">{t('launchpad.subtitle')}</p>
            </div>
         </div>

         <div className="flex items-center gap-2 mb-8 flex-wrap justify-center">
            <FilterTab label={t('launchpad.tabAll')} id="all" activeTab={activeTab} onClick={setActiveTab} />
            <FilterTab label={t('launchpad.tabText')} id="text" activeTab={activeTab} onClick={setActiveTab} />
            <FilterTab label={t('launchpad.tabMultimodal')} id="multimodal" activeTab={activeTab} onClick={setActiveTab} />
            <FilterTab label={t('launchpad.tabLocal')} id="local" activeTab={activeTab} onClick={setActiveTab} />
         </div>

         <div className="w-full flex flex-col border-t border-[var(--border-color)]">
            {filteredModels.length === 0 ? (
               <div className="py-8 text-center text-[var(--text-secondary)]">
                  <p className="text-sm">{t('launchpad.noMatch')}</p>
               </div>
            ) : (
               filteredModels.map((model) => (
                  <ModelRow
                     key={model.id}
                     title={t(model.titleKey)}
                     desc={t(model.descKey)}
                     icon={model.icon}
                     iconBg={model.iconBg}
                     badges={model.badgeKeys.map((b) => ({ text: t(b.textKey), color: b.color }))}
                     onClick={() => handleModelClick(model.providerId, t(model.titleKey))}
                     isConfigured={isProviderConfigured(model.providerId)}
                  />
               ))
            )}
         </div>

         {sessions.length > 0 && (
            <div className="w-full mt-8">
               <h2 className="text-sm font-semibold text-[var(--text-secondary)] mb-4">{t('launchpad.recentSessions')}</h2>
               <div className="w-full flex flex-col border border-[var(--border-color)] rounded-lg overflow-hidden">
                  {isLoadingSessions ? (
                     <div className="p-4 text-center text-[var(--text-secondary)]">
                        <Loader2 size={20} className="animate-spin mx-auto" />
                     </div>
                  ) : (
                     sessions
                        .filter((session) => session.message_count > 0)
                        .slice(0, 3)
                        .map((session) => (
                           <div
                              key={session.id}
                              onClick={() => onSelectSession(session.id)}
                              className="flex items-center justify-between px-4 py-3 hover:bg-[var(--bg-hover)] cursor-pointer transition-colors border-b border-[var(--border-color)] last:border-b-0 group"
                           >
                              <div className="flex-1 min-w-0">
                                 <p className="text-sm font-medium text-[var(--text-primary)] truncate">{session.title}</p>
                                 <p className="text-xs text-[var(--text-secondary)]">
                                    {t('sidebar.messageCount', { count: session.message_count })} ·{' '}
                                    {new Date(session.updated_at).toLocaleDateString(i18n.language)}
                                 </p>
                              </div>
                              <button
                                 onClick={(e) => onDeleteSession(session.id, e)}
                                 className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-500/10 rounded-md text-[var(--text-secondary)] hover:text-red-500 transition-all"
                              >
                                 <Trash2 size={14} />
                              </button>
                           </div>
                        ))
                  )}
               </div>
            </div>
         )}
      </div>
   );
}

function FilterTab({
   label,
   id,
   activeTab,
   onClick,
}: {
   label: string;
   id: string;
   activeTab: string;
   onClick: (id: string) => void;
}) {
   const isActive = activeTab === id;
   return (
      <button
         onClick={() => onClick(id)}
         className={cn(
            'px-4 py-1.5 rounded-full text-xs font-medium transition-all duration-200',
            isActive
               ? 'bg-[var(--text-primary)] text-[var(--bg-main)]'
               : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]',
         )}
      >
         {label}
      </button>
   );
}

function ModelRow({
   title,
   desc,
   icon,
   iconBg,
   badges,
   onClick,
   isConfigured,
}: {
   title: string;
   desc: string;
   icon: React.ReactNode;
   iconBg: string;
   badges: { text: string; color: 'blue' | 'green' | 'purple' | 'orange' | 'grey' }[];
   onClick: () => void;
   isConfigured?: boolean;
}) {
   const { t } = useTranslation();

   const getBadgeColor = (color: string) => {
      switch (color) {
         case 'green':
            return 'text-green-500 bg-green-500/10';
         case 'blue':
            return 'text-blue-500 bg-blue-500/10';
         case 'purple':
            return 'text-purple-500 bg-purple-500/10';
         case 'orange':
            return 'text-orange-500 bg-orange-500/10';
         default:
            return 'text-[var(--text-secondary)] bg-[var(--bg-hover)]';
      }
   };

   return (
      <div
         onClick={onClick}
         className="group flex items-center min-h-[72px] px-4 py-3 border-b border-[var(--border-color)] last:border-0 hover:bg-[var(--bg-hover)] transition-colors duration-200 cursor-pointer -mx-4 rounded-lg"
      >
         <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center shrink-0', iconBg)}>{icon}</div>
         <div className="flex-1 min-w-0 ml-4 flex flex-col justify-center gap-1">
            <div className="flex items-center gap-2 flex-wrap">
               <span className="text-sm font-bold text-[var(--text-primary)]">{title}</span>
               <div className="flex items-center gap-1.5">
                  {badges.map((b, i) => (
                     <span key={i} className={cn('text-[10px] px-1.5 py-0.5 rounded-sm font-medium', getBadgeColor(b.color))}>
                        {b.text}
                     </span>
                  ))}
                  {isConfigured !== undefined && (
                     <span
                        className={cn(
                           'text-[10px] px-1.5 py-0.5 rounded-sm font-medium',
                           isConfigured ? 'text-green-600 bg-green-500/10' : 'text-amber-600 bg-amber-500/10',
                        )}
                     >
                        {isConfigured ? t('launchpad.statusConfigured') : t('launchpad.statusPending')}
                     </span>
                  )}
               </div>
            </div>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{desc}</p>
         </div>
      </div>
   );
}

function ThinkingBlock({ text, isStreaming, isDarkMode }: { text: string, isStreaming?: boolean, isDarkMode: boolean }) {
   const [isOpen, setIsOpen] = useState(false); // collapsed by default
   const { t } = useTranslation();

   return (
      <Collapsible
         open={isOpen}
         onOpenChange={setIsOpen}
         className={cn(
            "w-full rounded-xl overflow-hidden border mb-2 transition-colors duration-200",
            isDarkMode ? "bg-[#1E1F20] border-[#2E2F31]" : "bg-gray-50 border-gray-200"
         )}
      >
         <CollapsibleTrigger asChild>
            <div className={cn(
               "w-full px-4 py-3 cursor-pointer transition-colors flex items-center justify-between group select-none",
               isDarkMode ? "hover:bg-[#252628]" : "hover:bg-gray-100"
            )}>
               <div className="flex items-center gap-2">
                  <Sparkles size={16} className="text-blue-400 fill-blue-400/20" />
                  <span className={cn(
                     "text-sm font-semibold",
                     isDarkMode ? "text-gray-200" : "text-gray-800"
                  )}>
                     {t('workspace.deepThinking')}
                     {isStreaming && <span className="animate-pulse ml-1">...</span>}
                  </span>
                  {!isOpen && (
                     <span className="text-xs text-gray-500 ml-2">{t('workspace.expandThinking')}</span>
                  )}
               </div>
               <div className={cn("text-gray-500 transition-transform duration-200", isOpen && "rotate-180")}>
                  <ChevronDown size={16} />
               </div>
            </div>
         </CollapsibleTrigger>
         <CollapsibleContent>
            <div className={cn(
               "px-4 pb-4 pt-1",
               isDarkMode ? "bg-[#1E1F20]" : "bg-gray-50"
            )}>
               <div className="relative pl-4 border-l-2 border-blue-500/30 ml-1">
                  <p className={cn(
                     "text-sm leading-relaxed whitespace-pre-wrap font-sans",
                     isDarkMode ? "text-gray-400" : "text-gray-600"
                  )}>
                     {text}
                     {isStreaming && <span className="inline-block w-1.5 h-4 ml-1 align-middle bg-blue-500 animate-pulse" />}
                  </p>
               </div>
            </div>
         </CollapsibleContent>
      </Collapsible>
   )
}

function ChatToolRunBlock({ run, isDarkMode }: { run: ChatToolRun; isDarkMode: boolean }) {
   const { t } = useTranslation();
   const isRunning = run.status === 'running';
   const isError = run.status === 'error';
   const label =
      run.tool_name === 'web_search' ? t('controlPanel.googleSearch')
      : run.tool_name === 'calculate' ? t('controlPanel.functionCall')
      : run.tool_name;

   return (
      <div className="rounded-lg border border-[var(--border-color)] overflow-hidden text-sm">
         <div className="flex items-center justify-between px-4 py-2 bg-[var(--bg-card)] border-b border-[var(--border-color)]">
            <div className="flex items-center gap-2">
               {run.tool_name === 'web_search' ? <Globe size={14} className="text-blue-400" /> : <Code size={14} className="text-emerald-400" />}
               <span className="font-medium text-[var(--text-primary)]">{label}</span>
            </div>
            {isRunning && <Loader2 size={14} className="animate-spin text-blue-400" />}
            {isError && <span className="text-xs text-red-500">{t('workspace.toolFailed')}</span>}
         </div>
         {run.tool_input && Object.keys(run.tool_input).length > 0 && (
            <pre className="px-4 py-2 text-xs font-mono text-[var(--text-secondary)] border-b border-[var(--border-color)] overflow-x-auto">
               {JSON.stringify(run.tool_input, null, 2)}
            </pre>
         )}
         {run.tool_output && (
            <pre className={cn(
               'px-4 py-3 text-xs font-mono overflow-x-auto max-h-48 overflow-y-auto',
               isDarkMode ? 'bg-[#0F172A] text-slate-300' : 'bg-slate-50 text-slate-700'
            )}>
               {run.tool_output}
            </pre>
         )}
      </div>
   );
}

function ToolExecutionBlock({ code, output, status, isDarkMode }: { code: string, output?: string, status: 'running' | 'completed', isDarkMode: boolean }) {
   const { t } = useTranslation();
   return (
      <div className="flex flex-col rounded-lg overflow-hidden border border-[var(--border-color)] w-full max-w-full animate-in zoom-in-95 duration-300">

         {/* Input */}
         <div className="bg-[var(--bg-card)]">
            <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--border-color)]">
               <div className="flex items-center gap-2">
                  <Terminal size={14} className="text-[var(--text-secondary)]" />
                  <span className="text-xs font-medium text-[var(--text-primary)]">{t('workspace.pythonCode')}</span>
               </div>
               <div className="flex items-center gap-3">
                  {status === 'running' && (
                     <div className="flex items-center gap-2 text-blue-400">
                        <Loader2 size={12} className="animate-spin" />
                        <span className="text-[10px] uppercase font-bold tracking-wider">{t('workspace.executing')}</span>
                     </div>
                  )}
                  <Badge variant="secondary" className="bg-[var(--bg-hover)] text-[var(--text-secondary)] text-[10px] h-5 rounded-sm">
                     pandas
                  </Badge>
               </div>
            </div>
            <div className="p-4 overflow-x-auto relative">
               <pre className="text-sm font-mono text-[var(--text-primary)]">{code}</pre>
               {status === 'running' && (
                  <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[var(--bg-hover)] to-transparent animate-shimmer" style={{ backgroundSize: '200% 100%' }}></div>
               )}
            </div>
         </div>

         {/* Output */}
         {output && (
            <div className={`border-t border-[var(--border-color)] p-4 animate-in slide-in-from-top-2 duration-300 ${isDarkMode ? 'bg-[#000000]' : 'bg-[#1e1e1e]'}`}>
               <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-medium text-[#8E9196] uppercase tracking-wider">{t('workspace.consoleOutput')}</span>
               </div>
               <div className="font-mono text-xs text-green-400 whitespace-pre-wrap">
                  {output}
               </div>
            </div>
         )}
      </div>
   )
}
