import { useEffect, useRef, useState } from 'react';
import { Loader2, Mic, Square, X } from 'lucide-react';
import { cn } from '@/components/ui/utils';
import { micSupported, WavRecorder } from '@/lib/wavRecorder';
import { getInterviewSttStatus, transcribeInterviewAudio } from '@/services/api';

type VoicePhase = 'idle' | 'recording' | 'transcribing';

type Props = {
  disabled?: boolean;
  onError: (message: string) => void;
  onTranscribed: (text: string) => void | Promise<void>;
};

function formatElapsed(ms: number): string {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}:${rem.toString().padStart(2, '0')}`;
}

export function VoiceAnswerControls({ disabled, onError, onTranscribed }: Props) {
  const [sttEnabled, setSttEnabled] = useState<boolean | null>(null);
  const [phase, setPhase] = useState<VoicePhase>('idle');
  const [elapsed, setElapsed] = useState(0);
  const recorderRef = useRef<WavRecorder | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const status = await getInterviewSttStatus();
        if (!cancelled) setSttEnabled(status.enabled);
      } catch {
        if (!cancelled) setSttEnabled(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return () => {
      if (tickRef.current) clearInterval(tickRef.current);
      recorderRef.current?.cancel();
    };
  }, []);

  const stopTick = () => {
    if (tickRef.current) {
      clearInterval(tickRef.current);
      tickRef.current = null;
    }
  };

  const finishAndSubmit = async () => {
    const recorder = recorderRef.current;
    if (!recorder) return;
    stopTick();
    setPhase('transcribing');
    try {
      const { blob } = await recorder.stop();
      recorderRef.current = null;
      const { text } = await transcribeInterviewAudio(blob);
      if (!text.trim()) {
        onError('没听到内容，请再说一次');
        setPhase('idle');
        setElapsed(0);
        return;
      }
      await onTranscribed(text.trim());
      setPhase('idle');
      setElapsed(0);
    } catch (err) {
      recorderRef.current = null;
      onError(err instanceof Error ? err.message : '语音识别失败');
      setPhase('idle');
      setElapsed(0);
    }
  };

  const start = async () => {
    if (disabled || phase !== 'idle') return;
    if (!micSupported()) {
      onError('当前环境不支持麦克风');
      return;
    }
    if (sttEnabled === false) {
      onError('未配置语音识别');
      return;
    }
    try {
      const recorder = new WavRecorder();
      recorderRef.current = recorder;
      await recorder.start(() => {
        void finishAndSubmit();
      });
      setPhase('recording');
      setElapsed(0);
      tickRef.current = setInterval(() => {
        setElapsed(recorder.elapsedMs());
      }, 200);
    } catch (err) {
      recorderRef.current?.cancel();
      recorderRef.current = null;
      onError(err instanceof Error ? err.message : '无法使用麦克风');
      setPhase('idle');
    }
  };

  const cancel = () => {
    stopTick();
    recorderRef.current?.cancel();
    recorderRef.current = null;
    setPhase('idle');
    setElapsed(0);
  };

  const unavailable = sttEnabled === false || !micSupported();
  const busy = phase === 'transcribing' || disabled;

  if (unavailable) {
    return (
      <button
        type="button"
        disabled
        title={sttEnabled === false ? '未配置语音识别（DASHSCOPE_API_KEY）' : '无法使用麦克风'}
        className="inline-flex items-center gap-2 rounded-xl border border-[var(--border-color)] px-4 py-2 text-sm text-[var(--text-secondary)] opacity-50"
      >
        <Mic className="h-4 w-4" />
        口述不可用
      </button>
    );
  }

  if (phase === 'recording') {
    return (
      <div className="inline-flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => void finishAndSubmit()}
          className="inline-flex items-center gap-2 rounded-xl bg-red-600 px-4 py-2 text-sm font-semibold text-white"
        >
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white/70" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-white" />
          </span>
          <Square className="h-3.5 w-3.5 fill-current" />
          结束并提交 · {formatElapsed(elapsed)}
        </button>
        <button
          type="button"
          onClick={cancel}
          className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--border-color)] px-3 py-2 text-sm text-[var(--text-secondary)]"
        >
          <X className="h-4 w-4" />
          取消
        </button>
      </div>
    );
  }

  if (phase === 'transcribing') {
    return (
      <button
        type="button"
        disabled
        className="inline-flex items-center gap-2 rounded-xl border border-[var(--border-color)] px-4 py-2 text-sm text-[var(--text-secondary)]"
      >
        <Loader2 className="h-4 w-4 animate-spin" />
        转写中…
      </button>
    );
  }

  return (
    <button
      type="button"
      disabled={busy || sttEnabled === null}
      onClick={() => void start()}
      className={cn(
        'inline-flex items-center gap-2 rounded-xl border border-[var(--border-color)] px-4 py-2 text-sm text-[var(--text-secondary)]',
        'hover:border-amber-500/40 hover:text-[var(--text-primary)] disabled:opacity-50',
      )}
    >
      <Mic className="h-4 w-4" />
      开始口述
    </button>
  );
}
