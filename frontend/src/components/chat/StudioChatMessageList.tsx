import type { RefObject } from 'react';
import { StudioAssistantMessage } from '@/components/chat/StudioAssistantMessage';
import { UserMessageBubble } from '@/components/chat/UserMessageBubble';
import type { StudioChatMessage } from '@/hooks/studioChat/types';

interface StudioChatMessageListProps {
  messages: StudioChatMessage[];
  isDarkMode: boolean;
  scrollSentinelRef: RefObject<HTMLDivElement | null>;
  onRecoveryRetry?: () => void;
  isRecoveryRetrying?: boolean;
}

export function StudioChatMessageList({
  messages,
  isDarkMode,
  scrollSentinelRef,
  onRecoveryRetry,
  isRecoveryRetrying = false,
}: StudioChatMessageListProps) {
  return (
    <div className="max-w-[900px] mx-auto py-6 sm:py-10 px-3 sm:px-6 flex flex-col gap-6 sm:gap-10">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className="flex flex-col gap-6 animate-in fade-in duration-500 slide-in-from-bottom-2"
        >
          {msg.role === 'user' ? (
            <UserMessageBubble variant="studio">
              {msg.images && msg.images.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-2">
                  {msg.images.map((image) => (
                    <div
                      key={image.id}
                      className="rounded-lg overflow-hidden border border-[var(--border-color)] cursor-pointer hover:opacity-80 transition-opacity"
                    >
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
              {msg.content && <p className="whitespace-pre-wrap">{msg.content}</p>}
            </UserMessageBubble>
          ) : (
            <StudioAssistantMessage
              thinking={msg.thinking}
              isThinking={msg.isThinking}
              toolRuns={msg.toolRuns}
              tool={msg.tool}
              content={msg.content}
              isDarkMode={isDarkMode}
              recoveryPrompt={msg.recoveryPrompt}
              onRecoveryRetry={msg.recoveryPrompt ? onRecoveryRetry : undefined}
              isRecoveryRetrying={isRecoveryRetrying}
            />
          )}
        </div>
      ))}

      <div ref={scrollSentinelRef} className="h-px w-full shrink-0" aria-hidden />
    </div>
  );
}
