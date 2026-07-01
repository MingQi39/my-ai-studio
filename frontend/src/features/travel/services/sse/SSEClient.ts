/**
 * Travel SSE — 复用共享 SSEClient，保留 Travel 事件类型。
 */
import { SSEClient as BaseSSEClient, type SSEClientOptions as BaseSSEClientOptions } from '@/lib/sseClient';
import type { SSEEvent } from '@/features/travel/types/events';

export type { SSEEvent };

export type SSEClientOptions = BaseSSEClientOptions<SSEEvent>;

export class SSEClient extends BaseSSEClient<SSEEvent> {
  constructor(options: SSEClientOptions) {
    super(options);
  }
}
