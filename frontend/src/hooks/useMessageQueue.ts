import { useCallback, useEffect, useRef, useState } from 'react';

export type QueuedMessage<T> = {
  id: string;
  payload: T;
};

export type MessageQueueSubmitResult = 'sent' | 'queued';

export function useMessageQueue<T>({
  isBusy,
  send,
}: {
  isBusy: boolean;
  send: (payload: T) => Promise<void> | void;
}) {
  const [queue, setQueue] = useState<QueuedMessage<T>[]>([]);
  const queueRef = useRef(queue);
  const isDispatchingRef = useRef(false);
  const sendRef = useRef(send);

  queueRef.current = queue;
  sendRef.current = send;

  const syncQueue = useCallback((next: QueuedMessage<T>[]) => {
    queueRef.current = next;
    setQueue(next);
  }, []);

  const enqueue = useCallback(
    (payload: T) => {
      syncQueue([
        ...queueRef.current,
        { id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, payload },
      ]);
    },
    [syncQueue],
  );

  const remove = useCallback(
    (id: string) => {
      syncQueue(queueRef.current.filter((item) => item.id !== id));
    },
    [syncQueue],
  );

  const update = useCallback(
    (id: string, payload: T) => {
      syncQueue(queueRef.current.map((item) => (item.id === id ? { ...item, payload } : item)));
    },
    [syncQueue],
  );

  const reorder = useCallback(
    (activeId: string, overId: string) => {
      const current = queueRef.current;
      const fromIndex = current.findIndex((item) => item.id === activeId);
      const toIndex = current.findIndex((item) => item.id === overId);
      if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) {
        return;
      }
      const next = [...current];
      const [moved] = next.splice(fromIndex, 1);
      next.splice(toIndex, 0, moved);
      syncQueue(next);
    },
    [syncQueue],
  );

  const submit = useCallback(
    async (payload: T): Promise<MessageQueueSubmitResult> => {
      if (isBusy || isDispatchingRef.current || queueRef.current.length > 0) {
        enqueue(payload);
        return 'queued';
      }

      isDispatchingRef.current = true;
      try {
        await sendRef.current(payload);
      } finally {
        isDispatchingRef.current = false;
      }
      return 'sent';
    },
    [enqueue, isBusy],
  );

  useEffect(() => {
    if (isBusy || isDispatchingRef.current || queueRef.current.length === 0) {
      return;
    }

    const [next, ...rest] = queueRef.current;
    syncQueue(rest);
    isDispatchingRef.current = true;

    void Promise.resolve(sendRef.current(next.payload))
      .catch((error) => {
        console.error('Queued message send failed:', error);
        syncQueue([next, ...queueRef.current]);
      })
      .finally(() => {
        isDispatchingRef.current = false;
      });
  }, [isBusy, queue.length, syncQueue]);

  return {
    queue,
    submit,
    remove,
    update,
    reorder,
    clear: () => syncQueue([]),
  };
}
