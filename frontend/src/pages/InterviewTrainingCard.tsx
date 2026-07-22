import { useState } from 'react';
import { Lightbulb, Loader2 } from 'lucide-react';

/** Compact answer card reused by Interview workbench flows. */
export function InterviewTrainingCard({
  question,
  focusNode,
  onSubmit,
}: {
  question: string;
  focusNode?: string;
  onSubmit: (answer: string) => Promise<void>;
}) {
  const [answer, setAnswer] = useState('');
  const [hint, setHint] = useState(false);
  const [saving, setSaving] = useState(false);

  return (
    <section className="rounded-2xl border border-[var(--border-color)] bg-[var(--bg-card)] p-6">
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-600">30 second prompt</p>
      <h2 className="mt-3 text-lg font-semibold text-[var(--text-primary)]">{question}</h2>
      {focusNode && (
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          本轮重点：<span className="font-mono text-amber-700 dark:text-amber-300">{focusNode}</span>
        </p>
      )}
      <textarea
        value={answer}
        onChange={(event) => setAnswer(event.target.value)}
        placeholder="用自己的话说，不用写标准答案…"
        className="mt-5 h-28 w-full rounded-xl border border-[var(--border-color)] bg-[var(--bg-main)] p-3 text-sm outline-none focus:border-amber-500/50"
      />
      {hint && (
        <p className="mt-3 rounded-xl bg-amber-500/10 px-3 py-2 text-sm text-amber-900 dark:text-amber-100">
          提示：先说适用场景，再说取舍，最后连到真实项目证据。
        </p>
      )}
      <div className="mt-4 flex gap-2">
        <button
          type="button"
          onClick={() => setHint(true)}
          className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--border-color)] px-4 py-2 text-sm text-[var(--text-secondary)]"
        >
          <Lightbulb className="h-4 w-4" />
          给一个提示
        </button>
        <button
          type="button"
          disabled={saving || !answer.trim()}
          onClick={async () => {
            setSaving(true);
            try {
              await onSubmit(answer);
              setAnswer('');
              setHint(false);
            } finally {
              setSaving(false);
            }
          }}
          className="inline-flex items-center gap-1.5 rounded-xl bg-amber-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          保存并进入复习
        </button>
      </div>
    </section>
  );
}
