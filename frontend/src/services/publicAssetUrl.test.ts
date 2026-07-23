import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  encodeAssetPath,
  originFromApiBase,
  resolvePublicAssetUrlWithOrigin,
} from './publicAssetUrl.ts';

describe('publicAssetUrl', () => {
  it('strips /api/v1 from API base', () => {
    assert.equal(originFromApiBase('http://43.143.251.51:8081/api/v1'), 'http://43.143.251.51:8081');
    assert.equal(originFromApiBase('http://127.0.0.1:10011/api/v1/'), 'http://127.0.0.1:10011');
  });

  it('encodes Chinese comic filenames', () => {
    assert.equal(
      encodeAssetPath('/interview/comics/01-什么是Agent.png'),
      '/interview/comics/01-%E4%BB%80%E4%B9%88%E6%98%AFAgent.png',
    );
  });

  it('keeps http page comics on the page origin', () => {
    const url = resolvePublicAssetUrlWithOrigin('/interview/comics/01-什么是Agent.png', {
      pageOrigin: 'http://localhost:11010',
      pageProtocol: 'http:',
      apiBase: 'http://localhost:11010/api/v1',
    });
    assert.equal(
      url,
      'http://localhost:11010/interview/comics/01-%E4%BB%80%E4%B9%88%E6%98%AFAgent.png',
    );
  });

  it('file:// Electron falls back to API host (not file:///interview/...)', () => {
    const url = resolvePublicAssetUrlWithOrigin('/interview/comics/01-什么是Agent.png', {
      pageOrigin: 'null',
      pageProtocol: 'file:',
      apiBase: 'http://43.143.251.51:8081/api/v1',
    });
    assert.equal(
      url,
      'http://43.143.251.51:8081/interview/comics/01-%E4%BB%80%E4%B9%88%E6%98%AFAgent.png',
    );
    assert.ok(url && !url.startsWith('file:'));
  });

  it('passes through absolute URLs', () => {
    assert.equal(
      resolvePublicAssetUrlWithOrigin('https://cdn.example/a.png', {
        pageProtocol: 'file:',
        apiBase: 'http://x/api/v1',
      }),
      'https://cdn.example/a.png',
    );
  });
});
