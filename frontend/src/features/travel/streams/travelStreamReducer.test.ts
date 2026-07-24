import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  createTravelStreamState,
  reduceTravelStreamEvent,
} from './travelStreamReducer.ts';

describe('travelStreamReducer', () => {
  it('rebuilds thinking steps and final content when buffered events are replayed', () => {
    const state = createTravelStreamState('agent');
    reduceTravelStreamEvent(state, {
      type: 'step',
      source: 'agent',
      timestamp: '',
      step_type: 'Observe',
      round: 1,
      sequence: 1,
      content: '观察天气',
    });
    reduceTravelStreamEvent(state, {
      type: 'final_response',
      source: 'agent',
      timestamp: '',
      content: '杭州旅行建议',
    });
    const done = reduceTravelStreamEvent(state, {
      type: 'done',
      source: 'agent',
      timestamp: '',
    });

    assert.equal(done.done, true);
    assert.equal(done.message?.content, '杭州旅行建议');
    assert.equal(done.message?.thinkingSteps?.[0]?.type, 'Observe');
    assert.equal(done.message?.thinkingSteps?.[0]?.content, '观察天气');
  });
});
