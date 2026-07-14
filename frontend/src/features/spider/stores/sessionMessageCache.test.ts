import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  patchGeneratingMessages,
  resolveMessagesAfterSwitch,
  stashSessionMessages,
  type CacheableChatMessage,
} from './sessionMessageCache.ts';

function msg(
  id: string,
  content: string,
  extra?: Record<string, unknown>,
): CacheableChatMessage {
  return { id, role: 'assistant', content, ...extra };
}

describe('sessionMessageCache', () => {
  it('keeps in-flight messages when switching away and back', () => {
    const sessionA = 'sess-a';
    const sessionB = 'sess-b';
    const liveMessages = [
      msg('user-1', '分析目标网站', { role: 'user' }),
      msg('assistant-1', '', {
        isThinking: true,
        statusLabel: 'code_generator 正在处理...',
      }),
    ];

    const afterLeaveA = stashSessionMessages({}, sessionA, liveMessages);
    const onB = resolveMessagesAfterSwitch(afterLeaveA, sessionB);
    assert.equal(onB.length, 0);

    const afterLeaveB = stashSessionMessages(afterLeaveA, sessionB, onB);
    const backToA = resolveMessagesAfterSwitch(afterLeaveB, sessionA);
    assert.equal(backToA.length, 2);
    assert.equal(backToA[1]?.statusLabel, 'code_generator 正在处理...');
  });

  it('applies stream patches to cache when user is on another session', () => {
    const sessionA = 'sess-a';
    const cached = [
      msg('user-1', '分析', { role: 'user' }),
      msg('assistant-1', '', { isThinking: true, statusLabel: 'thinking' }),
    ];

    const patched = patchGeneratingMessages({
      messages: [],
      messageCache: { [sessionA]: cached },
      currentSessionId: 'sess-b',
      generatingSessionId: sessionA,
      messageId: 'assistant-1',
      updates: { statusLabel: 'code_generator 正在处理...' },
    });

    assert.equal(patched.messages.length, 0);
    assert.equal(
      patched.messageCache[sessionA]?.[1]?.statusLabel,
      'code_generator 正在处理...',
    );
  });
});
