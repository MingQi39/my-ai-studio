import { useTranslation } from 'react-i18next';
import { ChatInputArea, type ChatInputAreaProps } from '@/components/chat/ChatInputArea';
import { MessageQueuePanel } from '@/components/chat/MessageQueuePanel';
import { useMessageQueue } from '@/hooks/useMessageQueue';

export type QueuedChatInputProps<T> = Omit<ChatInputAreaProps, 'onSubmit' | 'disabled' | 'placeholder'> & {
  value: string;
  onChange: (value: string) => void;
  isBusy: boolean;
  onStop?: () => void;
  disabled?: boolean;
  placeholder?: string;
  busyPlaceholder?: string;
  getPayload: (value: string) => T | null;
  onSendPayload: (payload: T) => Promise<void> | void;
  getQueuedLabel: (payload: T) => string;
  onQueuedEdit?: (payload: T) => void;
  shouldBypassQueue?: (payload: T) => boolean;
  queueClassName?: string;
};

export function QueuedChatInput<T>({
  value,
  onChange,
  isBusy,
  onStop,
  disabled = false,
  placeholder,
  busyPlaceholder,
  getPayload,
  onSendPayload,
  getQueuedLabel,
  onQueuedEdit,
  shouldBypassQueue,
  queueClassName,
  ...inputProps
}: QueuedChatInputProps<T>) {
  const { t } = useTranslation();
  const { queue, submit, remove, reorder } = useMessageQueue({
    isBusy,
    send: onSendPayload,
  });

  const handleSubmit = () => {
    const payload = getPayload(value);
    if (payload == null) return;

    // Clear immediately — send handlers often await long-running streams.
    onChange('');

    if (shouldBypassQueue?.(payload)) {
      void Promise.resolve(onSendPayload(payload));
      return;
    }

    void submit(payload);
  };

  const handleEditQueued = (id: string, payload: T) => {
    remove(id);
    onQueuedEdit?.(payload);
  };

  return (
    <div className="space-y-2">
      <MessageQueuePanel
        queue={queue}
        getLabel={getQueuedLabel}
        onRemove={remove}
        onReorder={reorder}
        onEdit={onQueuedEdit ? handleEditQueued : undefined}
        className={queueClassName}
      />
      <ChatInputArea
        {...inputProps}
        value={value}
        onChange={onChange}
        onSubmit={handleSubmit}
        isGenerating={isBusy}
        onStop={onStop}
        disabled={disabled}
        placeholder={
          isBusy ? (busyPlaceholder ?? t('chat.queue.followUpPlaceholder')) : placeholder
        }
      />
    </div>
  );
}
