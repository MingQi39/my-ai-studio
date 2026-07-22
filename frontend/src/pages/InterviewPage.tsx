import { useEffect, useRef, useState, type ReactNode } from 'react';
import {
  ArrowRight,
  Check,
  FileUp,
  Lightbulb,
  Loader2,
  Map,
  SkipForward,
  X,
} from 'lucide-react';
import {
  abandonInterviewAttempt,
  ApiError,
  commitInterviewAttempt,
  confirmInterviewClaim,
  craftInterviewResume,
  createInterviewAttempt,
  extractResume,
  getActiveInterviewAttempt,
  getInterviewAttemptHint,
  getInterviewProfile,
  getInterviewTrainingProgress,
  getResumeEligibility,
  listInterviewClaims,
  listReviewCards,
  saveInterviewClaim,
  submitInterviewAttemptAnswer,
  updateInterviewProfile,
  type InterviewAttempt,
  type InterviewFeedback,
  type InterviewReviewCard,
  type InterviewTrainingProgress,
  type ResumeCandidate,
  type ResumeEligibility,
} from '@/services/api';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

type Phase = 'loading' | 'setup' | 'import' | 'confirm' | 'train';
type Level = 'P5' | 'P6' | 'P7';
type Difficulty = '初级' | '中级' | '高级';
type BusyKind = false | 'loading' | 'submitting' | 'hinting' | 'committing';

const ROLE_OPTIONS = ['前端', '全栈', '后端', 'AI 应用工程'] as const;
const DIFFICULTY_OPTIONS: { label: Difficulty; level: Level; desc: string }[] = [
  { label: '初级', level: 'P5', desc: '定位与基础表达' },
  { label: '中级', level: 'P6', desc: '机制与取舍' },
  { label: '高级', level: 'P7', desc: '工程证据与风险' },
];
const SALARY_OPTIONS = ['15-25k', '25-40k', '40-60k', '60k+'] as const;
const CATEGORY_LABEL: Record<ResumeCandidate['category'], string> = {
  skill: '技术',
  project: '项目经历',
  role: '工作经历',
};

function difficultyToLevel(difficulty: Difficulty): Level {
  return DIFFICULTY_OPTIONS.find((d) => d.label === difficulty)?.level ?? 'P6';
}

function levelToDifficulty(level: string | null | undefined): Difficulty {
  if (level === '初级' || level === 'P5') return '初级';
  if (level === '高级' || level === 'P7') return '高级';
  if (level === '中级' || level === 'P6') return '中级';
  return '中级';
}

/** 答题路径节点：后端仍用英文 ID，界面显示简洁中文 */
const ROUTE_NODE_LABELS: Record<string, string> = {
  Position: '解决什么问题',
  Principle: '底层原理',
  Mechanism: '怎么实现',
  'Trade-off': '方案取舍',
  Evidence: '项目证据',
};

function routeNodeLabel(node: string): string {
  return ROUTE_NODE_LABELS[node] ?? node;
}

const TIER_LABEL: Record<InterviewTrainingProgress['goal']['tier'], string> = {
  low: '入门',
  mid: '中级',
  high: '高薪',
};

function MetricBar({ value, max = 1 }: { value: number; max?: number }) {
  const pct = Math.max(0, Math.min(100, max > 0 ? (value / max) * 100 : 0));
  return (
    <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-[var(--border-color)]/60">
      <div className="h-full rounded-full bg-amber-500/80 transition-[width] duration-300" style={{ width: `${pct}%` }} />
    </div>
  );
}

function ProgressPanel({
  progress,
  onStartModule,
  onProjectSim,
}: {
  progress: InterviewTrainingProgress;
  onStartModule?: (topic: string) => void;
  onProjectSim?: () => void;
}) {
  const [openDetail, setOpenDetail] = useState(false);
  const { coverage, route_depth: depth, retention, expectations, next_step, composite, weekly_trend, learning_path } =
    progress;
  const maxCommit = Math.max(1, ...weekly_trend.map((w) => w.committed_count));
  const metCount = expectations.filter((e) => e.met).length;
  const hasTrend = weekly_trend.some((w) => w.committed_count > 0);
  const nextMod = learning_path?.next_module;

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-medium tracking-wide text-[var(--text-secondary)]">
            综合进展 · {TIER_LABEL[progress.goal.tier]}对齐
          </p>
          <p className="mt-1 text-3xl font-semibold tabular-nums leading-none text-[var(--text-primary)]">
            {composite.score}
            <span className="ml-1 text-sm font-normal text-[var(--text-secondary)]">/100</span>
          </p>
        </div>
        <p className="max-w-[9rem] text-right text-[10px] leading-snug text-[var(--text-secondary)]">
          仅计完成闭环与复习
        </p>
      </div>

      {nextMod && (
        <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-main)] p-3">
          <p className="text-[10px] font-medium tracking-wide text-[var(--text-secondary)]">
            学习路线 · {learning_path?.done_count ?? 0}/{learning_path?.total_relevant ?? 0} 阶段
          </p>
          <p className="mt-1 text-sm font-medium text-[var(--text-primary)]">下一模块：{nextMod.title}</p>
          <p className="mt-1 text-[11px] leading-relaxed text-[var(--text-secondary)]">{nextMod.reason}</p>
          <div className="mt-2.5 flex flex-wrap gap-2">
            {onStartModule && (
              <button
                type="button"
                onClick={() => onStartModule(nextMod.topic)}
                className="rounded-lg bg-amber-500/15 px-2.5 py-1.5 text-[11px] font-semibold text-amber-800 dark:text-amber-200"
              >
                练 {nextMod.topic}
              </button>
            )}
            {onProjectSim && (
              <button
                type="button"
                onClick={onProjectSim}
                className="rounded-lg border border-[var(--border-color)] px-2.5 py-1.5 text-[11px] text-[var(--text-primary)]"
              >
                项目模拟
              </button>
            )}
          </div>
        </div>
      )}

      <div className="space-y-4">
        <div>
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-xs text-[var(--text-primary)]">主题覆盖</span>
            <span className="text-xs tabular-nums text-[var(--text-secondary)]">
              {coverage.covered_count}/{coverage.total_count}
            </span>
          </div>
          <MetricBar value={coverage.covered_count} max={Math.max(1, coverage.total_count)} />
        </div>
        <div>
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-xs text-[var(--text-primary)]">闭环深度</span>
            <span className="text-xs tabular-nums text-[var(--text-secondary)]">
              近{depth.window_days}天 {depth.committed_count} 次
            </span>
          </div>
          <MetricBar
            value={depth.tradeoff_rate * 0.6 + depth.evidence_rate * 0.4}
            max={1}
          />
          <p className="mt-1 text-[10px] text-[var(--text-secondary)]">
            取舍 {Math.round(depth.tradeoff_rate * 100)}% · 证据 {Math.round(depth.evidence_rate * 100)}%
          </p>
        </div>
        <div>
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-xs text-[var(--text-primary)]">复习健康</span>
            <span className="text-xs tabular-nums text-[var(--text-secondary)]">
              到期 {retention.due_count} · 巩固 {retention.consolidated_count}
            </span>
          </div>
          <MetricBar value={retention.healthy_ratio} max={1} />
        </div>
      </div>

      <p className="rounded-xl bg-amber-500/10 px-3 py-2.5 text-[12px] leading-relaxed text-amber-900 dark:text-amber-100">
        {next_step}
      </p>

      <button
        type="button"
        onClick={() => setOpenDetail((v) => !v)}
        className="flex w-full items-center justify-between rounded-lg py-1 text-left text-[11px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
      >
        <span>
          期望清单 {metCount}/{expectations.length}
          {hasTrend ? ' · 周趋势' : ''}
          {composite.cap_reason ? ' · 有封顶说明' : ''}
        </span>
        <span className="tabular-nums">{openDetail ? '收起' : '展开'}</span>
      </button>

      {openDetail && (
        <div className="space-y-4 border-t border-[var(--border-color)] pt-4">
          <ul className="space-y-2.5">
            {expectations.map((item) => (
              <li key={item.id} className="flex gap-2 text-[11px] leading-snug">
                <span className={`mt-0.5 ${item.met ? 'text-emerald-600' : 'text-[var(--text-secondary)]'}`}>
                  {item.met ? '✓' : '○'}
                </span>
                <span>
                  <span className="text-[var(--text-primary)]">{item.label}</span>
                  <span className="mt-0.5 block text-[var(--text-secondary)]">{item.detail}</span>
                </span>
              </li>
            ))}
          </ul>

          {hasTrend && (
            <div>
              <p className="mb-2 text-[11px] text-[var(--text-secondary)]">近几周闭环次数</p>
              <div className="flex h-12 items-end gap-1.5">
                {weekly_trend.map((w) => (
                  <div
                    key={w.week_start}
                    className="flex-1 rounded-sm bg-amber-500/55"
                    style={{
                      height: `${Math.max(6, (w.committed_count / maxCommit) * 100)}%`,
                    }}
                    title={`${w.week_start}: ${w.committed_count}`}
                  />
                ))}
              </div>
            </div>
          )}

          <p className="text-[10px] leading-relaxed text-[var(--text-secondary)]">
            {composite.formula}
            {composite.cap_reason ? ` · ${composite.cap_reason}` : ''}
          </p>
        </div>
      )}
    </div>
  );
}

function AtlasPath({ nodes, focus }: { nodes: string[]; focus?: string }) {
  return (
    <ol className="flex flex-wrap items-center gap-x-1 gap-y-2 text-[13px]">
      {nodes.map((node, index) => {
        const active = focus
          ? node === focus || node.toLowerCase().includes(focus.toLowerCase())
          : index === Math.min(2, nodes.length - 1);
        return (
          <li key={`${node}-${index}`} className="flex items-center gap-1">
            {index > 0 && <span className="px-0.5 text-[var(--text-secondary)] opacity-40">→</span>}
            <span
              className={
                active
                  ? 'rounded-md bg-amber-500/15 px-2 py-0.5 font-semibold text-amber-700 dark:text-amber-300'
                  : 'rounded-md px-2 py-0.5 text-[var(--text-secondary)]'
              }
            >
              {routeNodeLabel(node)}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function RouteChecklist({
  nodes,
  covered,
  missing,
  focus,
}: {
  nodes: string[];
  covered: string[];
  missing: string[];
  focus?: string;
}) {
  return (
    <ul className="space-y-2">
      {nodes.map((node) => {
        const done = covered.includes(node);
        const gap = missing.includes(node);
        const isFocus = focus === node;
        return (
          <li
            key={node}
            className={`flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm ${
              isFocus ? 'bg-amber-500/10 text-amber-800 dark:text-amber-200' : 'text-[var(--text-primary)]'
            }`}
          >
            <span
              className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${
                done
                  ? 'bg-emerald-600 text-white'
                  : gap
                    ? 'border border-dashed border-[var(--border-color)] text-[var(--text-secondary)]'
                    : 'border border-[var(--border-color)] text-[var(--text-secondary)]'
              }`}
            >
              {done ? '✓' : '○'}
            </span>
            <span>{routeNodeLabel(node)}</span>
            {isFocus && (
              <span className="ml-auto text-[11px] tracking-wide text-amber-600">当前重点</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function Panel({
  title,
  eyebrow,
  children,
  className = '',
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`flex min-h-0 flex-col rounded-2xl border border-[var(--border-color)] bg-[var(--bg-card)] ${className}`}
    >
      <header className="border-b border-[var(--border-color)] px-5 py-4">
        {eyebrow && (
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--text-secondary)]">
            {eyebrow}
          </p>
        )}
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h2>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto p-5">{children}</div>
    </section>
  );
}

function ChoiceGroup({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div>
      <p className="text-sm font-medium text-[var(--text-primary)]">{label}</p>
      <div className="mt-3 flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

function ChoiceButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg px-3 py-1.5 text-sm transition ${
        active
          ? 'bg-[var(--text-primary)] text-[var(--bg-card)]'
          : 'border border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
      }`}
    >
      {children}
    </button>
  );
}

export function InterviewPage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<Phase>('loading');
  const [busy, setBusy] = useState<BusyKind>(false);
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<ResumeCandidate[]>([]);
  const [targetRole, setTargetRole] = useState('全栈');
  const [customRole, setCustomRole] = useState('');
  const [difficulty, setDifficulty] = useState<Difficulty>('中级');
  const [salaryBand, setSalaryBand] = useState<string>('25-40k');
  const [level, setLevel] = useState<Level>('P6');
  const [attempt, setAttempt] = useState<InterviewAttempt | null>(null);
  const [answer, setAnswer] = useState('');
  const [feedback, setFeedback] = useState<InterviewFeedback | null>(null);
  const [hintLevel, setHintLevel] = useState(0);
  const [hintText, setHintText] = useState<string | null>(null);
  const [cards, setCards] = useState<InterviewReviewCard[]>([]);
  const [topics, setTopics] = useState<string[]>([]);
  const [customTopic, setCustomTopic] = useState('');
  const [hasResumeClaims, setHasResumeClaims] = useState(false);
  const [progress, setProgress] = useState<InterviewTrainingProgress | null>(null);
  const [comicLightbox, setComicLightbox] = useState<{ src: string; alt: string } | null>(null);
  const [resumeEligibility, setResumeEligibility] = useState<ResumeEligibility | null>(null);
  const [resumeMarkdown, setResumeMarkdown] = useState('');
  const [resumeOpen, setResumeOpen] = useState(false);
  const [resumeBusy, setResumeBusy] = useState(false);
  const [resumeWarn, setResumeWarn] = useState<string[] | null>(null);
  const recentQuestionsRef = useRef<string[]>([]);

  const resolvedRole = customRole.trim() || targetRole;
  const training = attempt;

  const refreshProgress = async () => {
    try {
      setProgress(await getInterviewTrainingProgress());
    } catch {
      // non-blocking
    }
    try {
      setResumeEligibility(await getResumeEligibility());
    } catch {
      // non-blocking
    }
  };

  const applyAttempt = (next: InterviewAttempt, opts?: { clearAnswer?: boolean }) => {
    setAttempt(next);
    setLevel(next.level);
    setFeedback(next.evaluation);
    setHintLevel(next.hint_level || 0);
    if (next.question) {
      const prev = recentQuestionsRef.current.filter((q) => q !== next.question);
      recentQuestionsRef.current = [...prev, next.question].slice(-8);
    }
    if (opts?.clearAnswer) {
      setAnswer('');
      setHintText(null);
    } else if (next.status === 'evaluated') {
      setAnswer('');
    } else if (next.status === 'open' || next.status === 'degraded') {
      const latest = [...(next.answers || [])].sort((a, b) => a.version - b.version).at(-1);
      setAnswer(latest?.text ?? '');
    } else if (next.status === 'reanswered') {
      const v2 = next.answers.find((a) => a.version === 2);
      setAnswer(v2?.text ?? '');
    }
    if (next.starter_topics?.length) {
      setTopics((prev) => {
        const merged = [...prev.filter((t) => !next.starter_topics!.includes(t)), ...next.starter_topics!];
        return merged.length ? merged : next.starter_topics!;
      });
    }
  };

  const goalStillMatches = (active: InterviewAttempt) => {
    const snap = active.goal_snapshot || {};
    const snapRole = (snap.target_role || '').trim();
    const role = resolvedRole.trim();
    if (snapRole && role && snapRole !== role) return false;

    const snapLevelRaw = (snap.target_level || '').trim();
    const normLevel = (v: string) =>
      v === 'P5' ? '初级' : v === 'P6' ? '中级' : v === 'P7' ? '高级' : v;
    const snapLevel = normLevel(snapLevelRaw);
    const currentLevel = normLevel(difficulty);
    if (snapLevel && currentLevel && snapLevel !== currentLevel) return false;

    const snapSalary = (snap.salary_band || '').trim();
    if (snapSalary && salaryBand && snapSalary !== salaryBand) return false;
    return true;
  };

  const enterTrain = async (
    nextLevel?: Level,
    topic?: string,
    mode: 'standard' | 'project_sim' = 'standard',
  ) => {
    const useLevel = nextLevel ?? level;
    const active = await getActiveInterviewAttempt();
    if (
      active &&
      mode === 'standard' &&
      (!topic || active.topic === topic) &&
      (active.training_mode ?? 'standard') !== 'project_sim' &&
      goalStillMatches(active)
    ) {
      applyAttempt(active);
      const [review, claims] = await Promise.all([listReviewCards(), listInterviewClaims()]);
      const confirmed = claims.filter((c) => c.status === 'confirmed');
      setHasResumeClaims(confirmed.length > 0);
      const starters = active.starter_topics?.length ? active.starter_topics : [];
      const resumeTopics = confirmed.map((c) => c.label);
      setTopics(
        resumeTopics.length
          ? [...resumeTopics, ...starters.filter((t) => !resumeTopics.includes(t))]
          : starters,
      );
      setCards(review);
      setPhase('train');
      void refreshProgress();
      return;
    }
    if (active) {
      await abandonInterviewAttempt(active.id, 'switch_topic');
    }
    const next = await createInterviewAttempt({ level: useLevel, topic, mode });
    applyAttempt(next, { clearAnswer: true });
    const [review, claims] = await Promise.all([listReviewCards(), listInterviewClaims()]);
    const confirmed = claims.filter((c) => c.status === 'confirmed');
    setHasResumeClaims(confirmed.length > 0);
    const starters = next.starter_topics?.length ? next.starter_topics : [];
    const resumeTopics = confirmed.map((c) => c.label);
    setTopics(
      resumeTopics.length
        ? [...resumeTopics, ...starters.filter((t) => !resumeTopics.includes(t))]
        : starters,
    );
    setCards(review);
    setPhase('train');
    void refreshProgress();
  };

  const boot = async () => {
    setError(null);
    try {
      const profile = await getInterviewProfile();
      if (profile.target_role) setTargetRole(profile.target_role);
      if (profile.target_level) {
        const d = levelToDifficulty(profile.target_level);
        setDifficulty(d);
        setLevel(difficultyToLevel(d));
      }
      if (profile.salary_band) setSalaryBand(profile.salary_band);

      if (profile.target_role && profile.target_level && profile.salary_band) {
        await enterTrain(difficultyToLevel(levelToDifficulty(profile.target_level)));
      } else {
        setPhase('setup');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
      setPhase('setup');
    }
  };

  useEffect(() => {
    void boot();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!comicLightbox) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setComicLightbox(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [comicLightbox]);

  const startWithGoal = async () => {
    if (!resolvedRole.trim() || !salaryBand) return;
    setBusy(true);
    setError(null);
    try {
      const nextLevel = difficultyToLevel(difficulty);
      setLevel(nextLevel);
      await updateInterviewProfile({
        target_role: resolvedRole.trim(),
        target_level: difficulty,
        salary_band: salaryBand,
      });
      await enterTrain(nextLevel);
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成题目失败');
    } finally {
      setBusy(false);
    }
  };

  const onUpload = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      const result = await extractResume(file);
      setCandidates(result.claims);
      setWarning(result.warning);
      setPhase('confirm');
    } catch (err) {
      setError(err instanceof Error ? err.message : '解析失败');
    } finally {
      setBusy(false);
    }
  };

  const removeCandidate = (index: number) => {
    setCandidates((prev) => prev.filter((_, i) => i !== index));
  };

  const confirmResumeEnrichment = async () => {
    if (!candidates.length) return;
    setBusy(true);
    setError(null);
    try {
      // Keep existing goal; resume only adds experience/skills.
      await updateInterviewProfile({
        target_role: resolvedRole.trim(),
        target_level: difficulty,
        salary_band: salaryBand,
        keywords: candidates.map((c) => c.label),
      });
      const saved = await Promise.all(candidates.map((c) => saveInterviewClaim(c)));
      await Promise.all(saved.map((c) => confirmInterviewClaim(c.id)));
      setHasResumeClaims(true);
      await enterTrain(level);
    } catch (err) {
      setError(err instanceof Error ? err.message : '确认失败');
    } finally {
      setBusy(false);
    }
  };

  const loadTraining = async (opts?: {
    topic?: string;
    level?: Level;
    exclude_questions?: string[];
    exclude_topics?: string[];
    abandon_reason?: 'skip_retry' | 'switch_topic' | 'change_question';
    mode?: 'standard' | 'project_sim';
  }) => {
    setBusy('loading');
    setError(null);
    try {
      const nextLevel = opts?.level ?? level;
      if (attempt && attempt.status !== 'committed' && attempt.status !== 'abandoned') {
        await abandonInterviewAttempt(attempt.id, opts?.abandon_reason ?? 'switch_topic');
      }
      const next = await createInterviewAttempt({
        level: nextLevel,
        topic: opts?.topic,
        exclude_questions: opts?.exclude_questions,
        exclude_topics: opts?.exclude_topics,
        mode: opts?.mode ?? 'standard',
      });
      applyAttempt(next, { clearAnswer: true });
      setCards(await listReviewCards());
      await refreshProgress();
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取题目失败');
    } finally {
      setBusy(false);
    }
  };

  const changeQuestion = async () => {
    // 换一题 = 同主题换下一道；左侧 tab 才是换分类
    const currentTopic = attempt?.topic ?? training?.topic;
    const exclude = [...recentQuestionsRef.current];
    if (attempt?.question && !exclude.includes(attempt.question)) {
      exclude.push(attempt.question);
    }
    await loadTraining({
      level,
      topic: currentTopic,
      exclude_questions: exclude,
      abandon_reason: 'change_question',
    });
  };

  const submitAnswer = async () => {
    if (!attempt || !answer.trim()) return;
    if (attempt.status === 'reanswered' || attempt.status === 'committed') return;
    setBusy('submitting');
    setError(null);
    setWarning(null);
    try {
      const version: 1 | 2 = attempt.status === 'evaluated' ? 2 : 1;
      const result = await submitInterviewAttemptAnswer(attempt.id, {
        text: answer.trim(),
        version,
      });
      applyAttempt(result.attempt, { clearAnswer: version === 1 && !result.attempt.evaluation?.complete });
      if (result.degraded) {
        setWarning('评估暂时不可用，答案已保存。可重试提交或跳过本题。');
      }
      if (version === 1 && result.attempt.status === 'evaluated') {
        setAnswer('');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '评估失败');
    } finally {
      setBusy(false);
    }
  };

  const requestHint = async () => {
    if (!attempt) return;
    // After L4, allow re-fetching L4 (fresh wording) instead of locking the button forever —
    // especially important after refresh when attempt.hint_level is already 4.
    const next = hintLevel >= 4 ? 4 : Math.min(hintLevel + 1, 4);
    setBusy('hinting');
    setError(null);
    try {
      const hint = await getInterviewAttemptHint(attempt.id, next);
      setHintLevel(next);
      setHintText(hint.content);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取提示失败');
    } finally {
      setBusy(false);
    }
  };

  const finishRound = async () => {
    if (!attempt) return;
    setBusy('committing');
    try {
      await commitInterviewAttempt(attempt.id);
      await loadTraining({ level });
      await refreshProgress();
    } catch (err) {
      setError(err instanceof Error ? err.message : '完成闭环失败');
      setBusy(false);
    }
  };

  const onCraftResume = async () => {
    setResumeBusy(true);
    setError(null);
    try {
      const result = await craftInterviewResume();
      setResumeMarkdown(result.markdown);
      setResumeWarn(result.warnings.length ? result.warnings : null);
      setResumeOpen(true);
      setResumeEligibility(await getResumeEligibility());
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        const detail = err.detail as unknown;
        const reasons =
          typeof detail === 'object' &&
          detail !== null &&
          'reasons' in detail &&
          Array.isArray((detail as { reasons: unknown }).reasons)
            ? ((detail as { reasons: string[] }).reasons)
            : resumeEligibility?.reasons;
        setError(reasons?.length ? reasons.join('；') : '暂不符合生成简历条件');
      } else {
        setError(err instanceof Error ? err.message : '生成简历失败');
      }
    } finally {
      setResumeBusy(false);
    }
  };

  const skipRetry = async () => {
    if (!attempt) return;
    setBusy('loading');
    try {
      await abandonInterviewAttempt(attempt.id, 'skip_retry');
      await loadTraining({ level });
    } catch (err) {
      setError(err instanceof Error ? err.message : '跳过失败');
      setBusy(false);
    }
  };

  if (phase === 'loading') {
    return (
      <main className="flex flex-1 items-center justify-center bg-[var(--bg-main)]">
        <Loader2 className="h-6 w-6 animate-spin text-[var(--text-secondary)]" />
      </main>
    );
  }

  if (phase === 'setup' || phase === 'import' || phase === 'confirm') {
    return (
      <main className="relative flex-1 overflow-y-auto bg-[var(--bg-main)]">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.35]"
          style={{
            backgroundImage:
              'linear-gradient(to right, var(--border-color) 1px, transparent 1px), linear-gradient(to bottom, var(--border-color) 1px, transparent 1px)',
            backgroundSize: '48px 48px',
          }}
        />
        <div className="relative mx-auto max-w-3xl px-6 py-12 md:py-16">
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-amber-600">Interview Navigator</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-[var(--text-primary)] md:text-4xl">
            {phase === 'confirm'
              ? '确认简历里的经历'
              : phase === 'import'
                ? '可选：补充简历经历'
                : '先定目标，再出题'}
          </h1>
          <p className="mt-3 max-w-xl text-[var(--text-secondary)]">
            {phase === 'confirm'
              ? '简历只补充工作/项目/技术事实。岗位、难度、薪资仍以你刚才设定的目标为准。'
              : phase === 'import'
                ? '上传后可多练项目与工作经历题；不上传也能按岗位目标继续练。'
                : '选择或输入目标岗位、难度与薪资区间，系统据此生成面试题。简历是可选增强。'}
          </p>

          {error && (
            <p className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-600">
              {error}
            </p>
          )}

          {phase === 'setup' && (
            <div className="mt-10 space-y-8">
              <ChoiceGroup label="目标岗位">
                {ROLE_OPTIONS.map((role) => (
                  <ChoiceButton
                    key={role}
                    active={!customRole && targetRole === role}
                    onClick={() => {
                      setCustomRole('');
                      setTargetRole(role);
                    }}
                  >
                    {role}
                  </ChoiceButton>
                ))}
              </ChoiceGroup>
              <input
                value={customRole}
                onChange={(e) => setCustomRole(e.target.value)}
                placeholder="或输入具体岗位，如「资深前端 / AI 全栈」"
                className="w-full rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] px-4 py-3 text-sm text-[var(--text-primary)] outline-none focus:border-amber-500/50"
              />

              <ChoiceGroup label="难度">
                {DIFFICULTY_OPTIONS.map((opt) => (
                  <ChoiceButton
                    key={opt.label}
                    active={difficulty === opt.label}
                    onClick={() => {
                      setDifficulty(opt.label);
                      setLevel(opt.level);
                    }}
                  >
                    {opt.label}
                    <span className="ml-1 opacity-60">· {opt.desc}</span>
                  </ChoiceButton>
                ))}
              </ChoiceGroup>

              <ChoiceGroup label="薪资区间">
                {SALARY_OPTIONS.map((band) => (
                  <ChoiceButton key={band} active={salaryBand === band} onClick={() => setSalaryBand(band)}>
                    {band}
                  </ChoiceButton>
                ))}
              </ChoiceGroup>

              <div className="flex flex-wrap gap-3 pt-2">
                <button
                  type="button"
                  disabled={busy || !resolvedRole.trim() || !salaryBand}
                  onClick={() => void startWithGoal()}
                  className="inline-flex items-center gap-2 rounded-xl bg-amber-600 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
                  生成面试题并开始
                </button>
                <button
                  type="button"
                  disabled={busy || !resolvedRole.trim() || !salaryBand}
                  onClick={async () => {
                    setBusy(true);
                    try {
                      await updateInterviewProfile({
                        target_role: resolvedRole.trim(),
                        target_level: difficulty,
                        salary_band: salaryBand,
                      });
                      setLevel(difficultyToLevel(difficulty));
                      setPhase('import');
                    } catch (err) {
                      setError(err instanceof Error ? err.message : '保存目标失败');
                    } finally {
                      setBusy(false);
                    }
                  }}
                  className="rounded-xl border border-[var(--border-color)] px-5 py-2.5 text-sm text-[var(--text-secondary)] disabled:opacity-50"
                >
                  先导入简历再出题
                </button>
              </div>
            </div>
          )}

          {phase === 'import' && (
            <div className="mt-10 space-y-4">
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void onUpload(file);
                }}
              />
              <button
                type="button"
                disabled={busy}
                onClick={() => fileRef.current?.click()}
                className="group flex w-full flex-col items-center justify-center rounded-2xl border border-dashed border-[var(--border-color)] bg-[var(--bg-card)] px-6 py-12 transition hover:border-amber-500/50"
              >
                {busy ? (
                  <Loader2 className="h-7 w-7 animate-spin text-amber-600" />
                ) : (
                  <FileUp className="h-7 w-7 text-[var(--text-secondary)] transition group-hover:text-amber-600" />
                )}
                <span className="mt-3 text-sm font-medium text-[var(--text-primary)]">上传 PDF / DOCX 简历</span>
                <span className="mt-1 text-xs text-[var(--text-secondary)]">
                  读取技术、工作与项目经历；岗位/难度/薪资沿用你的目标设定
                </span>
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void startWithGoal()}
                className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-amber-600 px-5 py-3 text-sm font-semibold text-white disabled:opacity-50"
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
                跳过简历，按目标直接出题
              </button>
              <button
                type="button"
                onClick={() => setPhase('setup')}
                className="w-full text-center text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              >
                返回修改目标
              </button>
            </div>
          )}

          {phase === 'confirm' && (
            <div className="mt-10 space-y-8">
              {warning && (
                <p className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] px-4 py-3 text-sm text-[var(--text-secondary)]">
                  {warning}
                </p>
              )}
              <p className="text-sm text-[var(--text-secondary)]">
                当前目标：{resolvedRole} · {difficulty} · {salaryBand}
              </p>
              {(['skill', 'project', 'role'] as const).map((category) => {
                const items = candidates
                  .map((item, index) => ({ item, index }))
                  .filter(({ item }) => item.category === category);
                if (!items.length) return null;
                return (
                  <div key={category}>
                    <p className="text-sm font-medium text-[var(--text-primary)]">{CATEGORY_LABEL[category]}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {items.map(({ item, index }) => (
                        <span
                          key={`${item.label}-${index}`}
                          className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-1.5 text-sm text-[var(--text-primary)]"
                        >
                          {item.label}
                          <button
                            type="button"
                            aria-label={`删除 ${item.label}`}
                            onClick={() => removeCandidate(index)}
                            className="text-[var(--text-secondary)] hover:text-red-500"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })}
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  disabled={busy || !candidates.length}
                  onClick={() => void confirmResumeEnrichment()}
                  className="inline-flex items-center gap-2 rounded-xl bg-amber-600 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                  确认经历并生成题目
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setCandidates([]);
                    setPhase('import');
                  }}
                  className="rounded-xl border border-[var(--border-color)] px-5 py-2.5 text-sm text-[var(--text-secondary)]"
                >
                  重新上传
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    );
  }

  const covered = feedback?.covered_nodes ?? [];
  const missing = feedback?.missing_nodes ?? training?.missing_nodes ?? [];
  const focus = feedback?.breakpoint ?? training?.focus_node;
  const snap = training?.goal_snapshot;
  const goalLine = [
    snap?.target_role || resolvedRole,
    snap?.target_level || difficulty,
    snap?.salary_band || salaryBand,
  ]
    .filter(Boolean)
    .join(' · ');
  const canSubmitV1 = attempt && ['open', 'degraded'].includes(attempt.status);
  const canSubmitV2 = attempt?.status === 'evaluated';
  const canCommit =
    attempt &&
    (attempt.status === 'reanswered' ||
      (attempt.status === 'evaluated' && attempt.evaluation?.complete));
  const showSkip =
    !!attempt &&
    (attempt.status === 'degraded' ||
      (attempt.status === 'evaluated' && !attempt.evaluation?.complete));

  return (
    <main className="flex flex-1 flex-col overflow-hidden bg-[var(--bg-main)]">
      <header className="flex flex-shrink-0 flex-wrap items-center gap-3 border-b border-[var(--border-color)] bg-[var(--bg-card)] px-5 py-3">
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-600">
            {goalLine || 'Workbench'} · 约 3 分钟
          </p>
          <h1 className="truncate text-lg font-semibold text-[var(--text-primary)]">
            {training
              ? `${training.training_mode === 'project_sim' ? '项目模拟 · ' : ''}今天练：${training.topic}`
              : '面试导航'}
          </h1>
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-[var(--border-color)] p-1">
          {DIFFICULTY_OPTIONS.map((opt) => (
            <button
              key={opt.label}
              type="button"
              onClick={() => {
                setDifficulty(opt.label);
                setLevel(opt.level);
                void (async () => {
                  await updateInterviewProfile({
                    target_role: resolvedRole.trim(),
                    target_level: opt.label,
                    salary_band: salaryBand,
                  });
                  await loadTraining({ level: opt.level, topic: training?.topic });
                })();
              }}
              className={`rounded-md px-2.5 py-1 text-xs ${
                difficulty === opt.label
                  ? 'bg-amber-500/15 font-semibold text-amber-700 dark:text-amber-300'
                  : 'text-[var(--text-secondary)]'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          disabled={!!busy}
          onClick={() => void changeQuestion()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-color)] px-3 py-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-50"
        >
          <SkipForward className="h-3.5 w-3.5" />
          换一题
        </button>
        <button
          type="button"
          disabled={!!busy}
          onClick={() => {
            void (async () => {
              if (attempt && attempt.status !== 'committed' && attempt.status !== 'abandoned') {
                try {
                  await abandonInterviewAttempt(attempt.id, 'switch_topic');
                } catch {
                  // 409 if already terminal — still leave train UI
                }
              }
              setAttempt(null);
              setFeedback(null);
              setAnswer('');
              setHintText(null);
              recentQuestionsRef.current = [];
              setPhase('setup');
            })();
          }}
          className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-50"
        >
          改目标
        </button>
        <button
          type="button"
          onClick={() => setPhase('import')}
          className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        >
          {hasResumeClaims ? '更新简历' : '补充简历'}
        </button>
        <button
          type="button"
          disabled={!resumeEligibility?.eligible || !!busy || resumeBusy}
          title={
            resumeEligibility && !resumeEligibility.eligible
              ? resumeEligibility.reasons.join('；')
              : '基于已确认事实与训练证据生成 Markdown 简历'
          }
          onClick={() => void onCraftResume()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-color)] px-3 py-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-50"
        >
          {resumeBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
          生成简历
        </button>
      </header>

      {error && (
        <p className="mx-5 mt-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-600">
          {error}
        </p>
      )}
      {warning && (
        <p className="mx-5 mt-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-800 dark:text-amber-100">
          {warning}
        </p>
      )}

      <div className="grid min-h-0 flex-1 gap-4 overflow-y-auto p-4 lg:grid-cols-[300px_minmax(0,1fr)_280px] lg:overflow-hidden">
        <div className="flex min-h-0 flex-col gap-4 lg:overflow-y-auto">
          <Panel title="训练进展" eyebrow="Progress">
            {progress ? (
              <ProgressPanel
                progress={progress}
                onStartModule={(topic) => void loadTraining({ topic, level })}
                onProjectSim={() => void loadTraining({ mode: 'project_sim', level, topic: 'Agent' })}
              />
            ) : (
              <p className="text-xs text-[var(--text-secondary)]">加载进展中…</p>
            )}
          </Panel>
          <Panel title="面试地图" eyebrow="Atlas">
          {training && (
            <>
              <p className="mb-3 text-xs text-[var(--text-secondary)]">当前问题在路径中的位置</p>
              <AtlasPath nodes={training.atlas} focus={training.topic} />
              {training.comic_url && (
                <button
                  type="button"
                  className="mt-3 block w-full overflow-hidden rounded-xl border border-[var(--border-color)] text-left"
                  onClick={() =>
                    setComicLightbox({
                      src: training.comic_url!,
                      alt: `${training.topic} 概念图`,
                    })
                  }
                  title="点击查看大图"
                >
                  <img
                    src={training.comic_url}
                    alt={`${training.topic} 概念图`}
                    className="max-h-36 w-full object-cover object-top"
                  />
                  <p className="px-2 py-1.5 text-[10px] text-[var(--text-secondary)]">模块入门漫画 · 点击放大</p>
                </button>
              )}
              {training.training_mode === 'project_sim' && training.structure_hint && (
                <p className="mt-3 rounded-lg bg-sky-500/10 px-2.5 py-2 text-[11px] leading-relaxed text-sky-900 dark:text-sky-100">
                  项目模拟 · {training.structure_hint}
                </p>
              )}
              <div className="my-5 h-px bg-[var(--border-color)]" />
              <p className="mb-2 text-xs font-medium text-[var(--text-secondary)]">
                {hasResumeClaims ? '目标题库 + 简历经历' : '按岗位生成的题库'}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {topics.slice(0, 12).map((topic) => (
                  <button
                    key={topic}
                    type="button"
                    onClick={() => {
                      if (topic !== training.topic) recentQuestionsRef.current = [];
                      void loadTraining({ topic, level });
                    }}
                    className={`rounded-md px-2 py-1 text-xs ${
                      training.topic === topic
                        ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300'
                        : 'bg-[var(--bg-main)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                    }`}
                  >
                    {topic}
                  </button>
                ))}
              </div>
              <form
                className="mt-3 flex gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  const topic = customTopic.trim();
                  if (!topic) return;
                  setTopics((prev) => (prev.includes(topic) ? prev : [topic, ...prev].slice(0, 12)));
                  setCustomTopic('');
                  void loadTraining({ topic, level });
                }}
              >
                <input
                  value={customTopic}
                  onChange={(e) => setCustomTopic(e.target.value)}
                  placeholder="自定义主题"
                  className="min-w-0 flex-1 rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] px-2.5 py-1.5 text-xs text-[var(--text-primary)] outline-none focus:border-amber-500/50"
                />
                <button
                  type="submit"
                  disabled={busy || !customTopic.trim()}
                  className="rounded-lg border border-[var(--border-color)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] disabled:opacity-50"
                >
                  练这个
                </button>
              </form>
              {cards.length > 0 && (
                <>
                  <div className="my-5 h-px bg-[var(--border-color)]" />
                  <p className="mb-2 flex items-center gap-1.5 text-xs font-medium text-[var(--text-secondary)]">
                    <Map className="h-3.5 w-3.5" />
                    待复习断点
                  </p>
                  <ul className="space-y-2">
                    {cards.slice(0, 5).map((card) => (
                      <li key={card.id}>
                        <button
                          type="button"
                          onClick={() => void loadTraining({ topic: card.topic, level })}
                          className="w-full rounded-lg border border-[var(--border-color)] px-3 py-2 text-left text-xs hover:border-amber-500/40"
                        >
                          <span className="font-medium text-[var(--text-primary)]">{card.topic}</span>
                          <span className="mt-1 block text-[var(--text-secondary)]">
                            {card.next_due_at ? `到期 · ` : ''}
                            卡在：
                            {card.missing_nodes.slice(0, 2).map(routeNodeLabel).join('、') || '—'}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
          </Panel>
        </div>

        <Panel title="当前练习" eyebrow="主动回忆" className="lg:overflow-hidden">
          {training && (
            <div className="flex h-full flex-col">
              <h3 className="text-xl font-semibold leading-snug text-[var(--text-primary)]">{training.question}</h3>
              <p className="mt-2 text-sm text-[var(--text-secondary)]">
                先自己说。重点走通「
                <span className="font-semibold text-amber-700 dark:text-amber-300">
                  {routeNodeLabel(training.focus_node)}
                </span>
                」，不要追求完整范文。
              </p>
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder={
                  canSubmitV2
                    ? '针对断点重答一版…'
                    : '开始说吧，短一点也没关系…'
                }
                disabled={attempt?.status === 'committed' || attempt?.status === 'abandoned'}
                className="mt-5 min-h-[160px] w-full flex-1 resize-none rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] p-4 text-sm text-[var(--text-primary)] outline-none focus:border-amber-500/50 disabled:opacity-60"
              />
              {hintText && (
                <p className="mt-3 rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-sm text-amber-900 dark:text-amber-100">
                  <Lightbulb className="mr-1.5 inline h-3.5 w-3.5" />
                  L{hintLevel} · {hintText}
                </p>
              )}
              <div className="mt-4 flex flex-wrap gap-2">
                {(canSubmitV1 || canSubmitV2) && (
                  <button
                    type="button"
                    disabled={!!busy || !answer.trim()}
                    onClick={() => void submitAnswer()}
                    className="inline-flex items-center gap-2 rounded-xl bg-amber-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                  >
                    {busy === 'submitting' ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <ArrowRight className="h-4 w-4" />
                    )}
                    {canSubmitV2 ? '提交重答' : '提交并看断点'}
                  </button>
                )}
                {canCommit && (
                  <button
                    type="button"
                    disabled={!!busy}
                    onClick={() => void finishRound()}
                    className="inline-flex items-center gap-2 rounded-xl bg-[var(--text-primary)] px-4 py-2 text-sm font-semibold text-[var(--bg-card)] disabled:opacity-50"
                  >
                    {busy === 'committing' ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Check className="h-4 w-4" />
                    )}
                    完成并保存复习卡
                  </button>
                )}
                {showSkip && (
                  <button
                    type="button"
                    disabled={!!busy}
                    onClick={() => void skipRetry()}
                    className="inline-flex items-center gap-2 rounded-xl border border-[var(--border-color)] px-4 py-2 text-sm text-[var(--text-secondary)]"
                  >
                    跳过（不计入闭环）
                  </button>
                )}
                <button
                  type="button"
                  disabled={!!busy || !attempt || attempt.status === 'committed'}
                  title={
                    hintLevel >= 4
                      ? '已到最深层，可再点一次换一版提示'
                      : feedback
                        ? '基于本题与你的答卷给出最小提示'
                        : '卡住了也可以点：先按本题给回忆方向（提交答卷后会更贴你的断点）'
                  }
                  onClick={() => void requestHint()}
                  className="inline-flex items-center gap-2 rounded-xl border border-[var(--border-color)] px-4 py-2 text-sm text-[var(--text-secondary)] disabled:opacity-50"
                >
                  <Lightbulb className="h-4 w-4" />
                  {hintLevel === 0
                    ? '给我提示'
                    : hintLevel >= 4
                      ? '再看提示'
                      : `再深一层 (${hintLevel}/4)`}
                </button>
              </div>
              {attempt?.status === 'degraded' && (
                <p className="mt-3 text-sm text-amber-700 dark:text-amber-200">
                  评估降级：答案已保留。可修改后再次提交，或跳过本题。
                </p>
              )}
            </div>
          )}
        </Panel>

        <Panel title="反馈与下一步" eyebrow="断点提示" className="lg:overflow-hidden">
          {training && (
            <>
              <RouteChecklist nodes={training.route_nodes} covered={covered} missing={missing} focus={focus} />
              {feedback ? (
                <div className="mt-5 space-y-3 rounded-xl border border-[var(--border-color)] bg-[var(--bg-main)] p-3 text-sm">
                  <p className="text-[var(--text-primary)]">{feedback.next_step}</p>
                  {feedback.hint && (
                    <p className="text-[var(--text-secondary)]">最小提示：{feedback.hint.recall}</p>
                  )}
                  {attempt?.status === 'evaluated' && !feedback.complete && (
                    <p className="text-xs text-[var(--text-secondary)]">
                      针对断点提交重答后，才能计入闭环并保存复习卡。
                    </p>
                  )}
                  {canCommit && (
                    <button
                      type="button"
                      disabled={!!busy}
                      onClick={() => void finishRound()}
                      className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--text-primary)] px-3 py-2 text-sm font-semibold text-[var(--bg-card)] disabled:opacity-50"
                    >
                      完成并保存复习卡
                    </button>
                  )}
                </div>
              ) : (
                <p className="mt-5 text-sm text-[var(--text-secondary)]">
                  先作答。提交后会标出已走通节点与当前断点，不会默认给完整答案。
                </p>
              )}
            </>
          )}
        </Panel>
      </div>

      <Dialog open={resumeOpen} onOpenChange={setResumeOpen}>
        <DialogContent className="max-w-2xl border-[var(--border-color)] bg-[var(--bg-card)]">
          <DialogHeader>
            <DialogTitle className="text-[var(--text-primary)]">生成的简历（Markdown）</DialogTitle>
          </DialogHeader>
          {resumeWarn?.length ? (
            <p className="text-xs text-amber-700 dark:text-amber-300">{resumeWarn.join(' · ')}</p>
          ) : null}
          <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-lg border border-[var(--border-color)] p-3 text-sm text-[var(--text-primary)]">
            {resumeMarkdown}
          </pre>
          <button
            type="button"
            onClick={() => void navigator.clipboard.writeText(resumeMarkdown)}
            className="inline-flex items-center justify-center rounded-lg border border-[var(--border-color)] px-3 py-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            复制
          </button>
        </DialogContent>
      </Dialog>

      {comicLightbox && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="漫画大图"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          onClick={() => setComicLightbox(null)}
        >
          <button
            type="button"
            className="absolute right-4 top-4 inline-flex h-10 w-10 items-center justify-center rounded-full bg-white/90 text-zinc-900 shadow"
            onClick={() => setComicLightbox(null)}
            aria-label="关闭"
          >
            <X className="h-5 w-5" />
          </button>
          <img
            src={comicLightbox.src}
            alt={comicLightbox.alt}
            className="max-h-[90vh] max-w-[min(960px,95vw)] rounded-lg object-contain shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </main>
  );
}
