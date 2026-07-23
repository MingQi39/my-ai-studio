import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  attemptCtaKind,
  goalCoreChanged,
  normalizeGoalCore,
} from './interviewGoalDraft.ts';

describe('interviewGoalDraft', () => {
  it('normalize trims role and salary', () => {
    const n = normalizeGoalCore({
      targetRole: '  前端  ',
      difficulty: '中级',
      salaryBand: ' 40-60k ',
    });
    assert.equal(n.targetRole, '前端');
    assert.equal(n.salaryBand, '40-60k');
  });

  it('goalCoreChanged is false when equal after normalize', () => {
    const saved = { targetRole: '前端', difficulty: '中级', salaryBand: '40-60k' };
    const draft = { targetRole: ' 前端 ', difficulty: '中级', salaryBand: '40-60k' };
    assert.equal(goalCoreChanged(saved, draft), false);
  });

  it('goalCoreChanged is true when role differs', () => {
    assert.equal(
      goalCoreChanged(
        { targetRole: '前端', difficulty: '中级', salaryBand: '40-60k' },
        { targetRole: '后端', difficulty: '中级', salaryBand: '40-60k' },
      ),
      true,
    );
  });

  it('attemptCtaKind switches only for non-terminal active statuses', () => {
    assert.equal(attemptCtaKind('answering'), 'switch');
    assert.equal(attemptCtaKind('evaluated'), 'switch');
    assert.equal(attemptCtaKind('committed'), 'generate');
    assert.equal(attemptCtaKind('abandoned'), 'generate');
    assert.equal(attemptCtaKind(null), 'generate');
  });
});
