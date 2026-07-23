export type GoalCore = {
  targetRole: string;
  difficulty: string;
  salaryBand: string;
};

export function normalizeGoalCore(g: GoalCore): GoalCore {
  return {
    targetRole: g.targetRole.trim(),
    difficulty: g.difficulty.trim(),
    salaryBand: g.salaryBand.trim(),
  };
}

export function goalCoreChanged(saved: GoalCore, draft: GoalCore): boolean {
  const a = normalizeGoalCore(saved);
  const b = normalizeGoalCore(draft);
  return (
    a.targetRole !== b.targetRole ||
    a.difficulty !== b.difficulty ||
    a.salaryBand !== b.salaryBand
  );
}

const ACTIVE = new Set([
  'open',
  'answering',
  'evaluated',
  'reanswered',
  'degraded',
]);

export type AttemptCtaKind = 'switch' | 'generate';

export function attemptCtaKind(status: string | null | undefined): AttemptCtaKind {
  if (status && ACTIVE.has(status)) return 'switch';
  return 'generate';
}
