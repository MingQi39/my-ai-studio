/** Record mono 16-bit PCM WAV from the microphone (browser / Electron). */

const TARGET_SAMPLE_RATE = 16000;
const MAX_DURATION_MS = 5 * 60 * 1000;

export type WavRecording = {
  blob: Blob;
  durationMs: number;
};

function writeString(view: DataView, offset: number, str: string) {
  for (let i = 0; i < str.length; i += 1) {
    view.setUint8(offset + i, str.charCodeAt(i));
  }
}

function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  writeString(view, 0, 'RIFF');
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(view, 8, 'WAVE');
  writeString(view, 12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(view, 36, 'data');
  view.setUint32(40, samples.length * 2, true);
  let offset = 44;
  for (let i = 0; i < samples.length; i += 1) {
    const s = Math.max(-1, Math.min(1, samples[i]!));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    offset += 2;
  }
  return new Blob([buffer], { type: 'audio/wav' });
}

function downsample(buffer: Float32Array, fromRate: number, toRate: number): Float32Array {
  if (fromRate === toRate) return buffer;
  const ratio = fromRate / toRate;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  for (let i = 0; i < newLength; i += 1) {
    const start = Math.floor(i * ratio);
    result[i] = buffer[start] ?? 0;
  }
  return result;
}

export function micSupported(): boolean {
  return typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia;
}

export class WavRecorder {
  private stream: MediaStream | null = null;
  private context: AudioContext | null = null;
  private processor: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private chunks: Float32Array[] = [];
  private startedAt = 0;
  private maxTimer: ReturnType<typeof setTimeout> | null = null;
  private onMaxDuration: (() => void) | null = null;

  async start(onMaxDuration?: () => void): Promise<void> {
    if (!micSupported()) {
      throw new Error('当前环境不支持麦克风');
    }
    this.onMaxDuration = onMaxDuration ?? null;
    this.chunks = [];
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    });
    const AudioCtx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    this.context = new AudioCtx();
    this.source = this.context.createMediaStreamSource(this.stream);
    // ScriptProcessor is deprecated but widely available; fine for short interview answers.
    this.processor = this.context.createScriptProcessor(4096, 1, 1);
    this.processor.onaudioprocess = (event) => {
      const input = event.inputBuffer.getChannelData(0);
      this.chunks.push(new Float32Array(input));
    };
    const silent = this.context.createGain();
    silent.gain.value = 0;
    this.source.connect(this.processor);
    this.processor.connect(silent);
    silent.connect(this.context.destination);
    this.startedAt = Date.now();
    this.maxTimer = setTimeout(() => {
      this.onMaxDuration?.();
    }, MAX_DURATION_MS);
  }

  elapsedMs(): number {
    if (!this.startedAt) return 0;
    return Date.now() - this.startedAt;
  }

  async stop(): Promise<WavRecording> {
    if (this.maxTimer) {
      clearTimeout(this.maxTimer);
      this.maxTimer = null;
    }
    const durationMs = this.elapsedMs();
    const context = this.context;
    const sampleRate = context?.sampleRate ?? TARGET_SAMPLE_RATE;
    const total = this.chunks.reduce((n, c) => n + c.length, 0);
    const merged = new Float32Array(total);
    let offset = 0;
    for (const chunk of this.chunks) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }
    this.cleanup();
    const down = downsample(merged, sampleRate, TARGET_SAMPLE_RATE);
    if (down.length === 0) {
      throw new Error('没听到内容，请再说一次');
    }
    return { blob: encodeWav(down, TARGET_SAMPLE_RATE), durationMs };
  }

  cancel(): void {
    if (this.maxTimer) {
      clearTimeout(this.maxTimer);
      this.maxTimer = null;
    }
    this.cleanup();
    this.chunks = [];
    this.startedAt = 0;
  }

  private cleanup(): void {
    try {
      this.processor?.disconnect();
    } catch {
      /* ignore */
    }
    try {
      this.source?.disconnect();
    } catch {
      /* ignore */
    }
    this.stream?.getTracks().forEach((t) => t.stop());
    void this.context?.close();
    this.processor = null;
    this.source = null;
    this.stream = null;
    this.context = null;
  }
}

export { MAX_DURATION_MS, TARGET_SAMPLE_RATE };
