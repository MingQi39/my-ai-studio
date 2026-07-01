/**
 * 通用 SSE 流式客户端 — 主对话与 Travel 共用。
 * 协议：HTTP POST/GET + text/event-stream，每行 `data: {json}`。
 */

export interface SSEClientOptions<T = unknown> {
  url: string;
  method?: 'GET' | 'POST';
  headers?: Record<string, string>;
  body?: string;
  onEvent: (event: T) => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
}

async function readResponseErrorDetail(response: Response): Promise<string> {
  let detail = response.statusText;
  try {
    const data = await response.json();
    if (typeof data.detail === 'string') return data.detail;
    if (typeof data.message === 'string') return data.message;
    if (data.detail !== undefined) return JSON.stringify(data.detail);
  } catch {
    try {
      const text = await response.text();
      if (text) return text;
    } catch {
      // ignore
    }
  }
  return detail;
}

function processSSEBuffer<T>(
  buffer: string,
  onRemainder: (remaining: string) => void,
  onEvent: (event: T) => void,
): void {
  const lines = buffer.split('\n');
  onRemainder(lines.pop() || '');

  for (const line of lines) {
    if (!line.startsWith('data: ')) continue;
    const data = line.slice(6).trim();
    if (!data) continue;
    try {
      onEvent(JSON.parse(data) as T);
    } catch (error) {
      console.error('Failed to parse SSE event:', data, error);
    }
  }
}

export class SSEClient<T = unknown> {
  private options: SSEClientOptions<T>;
  private cancelled = false;
  private abortController: AbortController | null = null;

  constructor(options: SSEClientOptions<T>) {
    this.options = {
      method: 'POST',
      ...options,
    };
  }

  async start(): Promise<void> {
    this.cancelled = false;
    this.abortController = new AbortController();

    try {
      await this.connect();
    } catch (error) {
      if (this.cancelled || (error instanceof DOMException && error.name === 'AbortError')) {
        return;
      }
      const message = error instanceof Error ? error.message : String(error);
      this.options.onError?.(new Error(message));
    } finally {
      this.abortController = null;
    }
  }

  cancel(): void {
    this.cancelled = true;
    this.abortController?.abort();
  }

  private async connect(): Promise<void> {
    const response = await fetch(this.options.url, {
      method: this.options.method,
      headers: {
        'Content-Type': 'application/json',
        ...this.options.headers,
      },
      body: this.options.body,
      signal: this.abortController?.signal,
    });

    if (!response.ok) {
      const detail = await readResponseErrorDetail(response);
      throw new Error(`HTTP ${response.status}: ${detail}`);
    }

    if (!response.body) {
      throw new Error('Response body is not readable');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (!this.cancelled) {
      let done: boolean;
      let value: Uint8Array | undefined;

      try {
        ({ done, value } = await reader.read());
      } catch (error) {
        if (this.cancelled || (error instanceof DOMException && error.name === 'AbortError')) {
          return;
        }
        throw error;
      }

      if (value) {
        buffer += decoder.decode(value, { stream: !done });
        processSSEBuffer(buffer, (remaining) => {
          buffer = remaining;
        }, this.options.onEvent);
      }

      if (done) {
        if (buffer.trim()) {
          processSSEBuffer(`${buffer}\n`, () => {
            buffer = '';
          }, this.options.onEvent);
        }
        if (!this.cancelled) {
          this.options.onComplete?.();
        }
        break;
      }
    }
  }
}
