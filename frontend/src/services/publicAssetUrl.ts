/**
 * Resolve app-public asset paths (e.g. /interview/comics/*.png).
 *
 * Electron production loads the UI from file://, so a root-relative comic URL
 * becomes file:///interview/comics/... and breaks. In that case we fall back to
 * the HTTP origin that serves the API (strip /api/v1).
 */

export function originFromApiBase(apiBase: string): string {
  return apiBase.replace(/\/?api\/v1\/?$/, '').replace(/\/$/, '');
}

export function encodeAssetPath(path: string): string {
  const normalized = path.startsWith('/') ? path : `/${path}`;
  return normalized
    .split('/')
    .map((seg, idx) => {
      if (idx === 0 || seg === '') return seg;
      try {
        return encodeURIComponent(decodeURIComponent(seg));
      } catch {
        return encodeURIComponent(seg);
      }
    })
    .join('/');
}

export function resolvePublicAssetUrlWithOrigin(
  path: string | null | undefined,
  opts: {
    pageOrigin?: string | null;
    pageProtocol?: string | null;
    apiBase: string;
  },
): string | null {
  if (!path) return null;
  if (/^(https?:|data:|blob:)/i.test(path)) return path;

  const encoded = encodeAssetPath(path);
  const protocol = opts.pageProtocol || '';
  const httpPage = protocol === 'http:' || protocol === 'https:';
  if (httpPage && opts.pageOrigin) {
    return `${opts.pageOrigin}${encoded}`;
  }

  const assetOrigin = originFromApiBase(opts.apiBase);
  if (/^https?:/i.test(assetOrigin)) {
    return `${assetOrigin}${encoded}`;
  }
  return encoded;
}
