import type { SSEEvent } from '@/features/travel/types/events';

export type { SSEEvent };

export interface SSEClientOptions {
  url: string;
  method?: 'GET' | 'POST';
  headers?: Record<string, string>;
  body?: string;
  onEvent: (event: SSEEvent) => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
  maxReconnectAttempts?: number;
  reconnectDelay?: number;
}

export class SSEClient {
  private options: SSEClientOptions;
  private cancelled = false;

  constructor(options: SSEClientOptions) {
    this.options = {
      method: 'POST',
      maxReconnectAttempts: 0,
      reconnectDelay: 1000,
      ...options,
    };
  }

  async start(): Promise<void> {
    this.cancelled = false;

    try {
      await this.connect();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      this.options.onError?.(new Error(message));
    }
  }

  private processBuffer(buffer: string, onRemainder: (remaining: string) => void): void {
    const lines = buffer.split('\n');
    onRemainder(lines.pop() || '');

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const data = line.slice(6).trim();
      if (!data) continue;
      try {
        const event = JSON.parse(data) as SSEEvent;
        this.options.onEvent(event);
      } catch (error) {
        console.error('Failed to parse SSE event:', data, error);
      }
    }
  }

  private async connect(): Promise<void> {
    const response = await fetch(this.options.url, {
      method: this.options.method,
      headers: {
        'Content-Type': 'application/json',
        ...this.options.headers,
      },
      body: this.options.body,
    });

    if (!response.ok) {
      let detail = response.statusText;
      try {
        const data = await response.json();
        detail =
          (typeof data.detail === 'string' && data.detail) ||
          (typeof data.message === 'string' && data.message) ||
          detail;
      } catch {
        try {
          detail = (await response.text()) || detail;
        } catch {
          // ignore
        }
      }
      throw new Error(`HTTP ${response.status}: ${detail}`);
    }

    if (!response.body) {
      throw new Error('Response body is null');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (!this.cancelled) {
      const { done, value } = await reader.read();

      if (value) {
        buffer += decoder.decode(value, { stream: !done });
        this.processBuffer(buffer, (remaining) => {
          buffer = remaining;
        });
      }

      if (done) {
        if (buffer.trim()) {
          this.processBuffer(`${buffer}\n`, () => {
            buffer = '';
          });
        }
        this.options.onComplete?.();
        break;
      }
    }
  }

  cancel(): void {
    this.cancelled = true;
  }
}
