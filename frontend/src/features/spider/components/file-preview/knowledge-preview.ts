export type KnowledgeFilePreviewKind = 'markdown' | 'text' | 'image' | 'pdf' | 'html' | 'office' | 'unsupported';

const OFFICE_ONLINE_EXTS = new Set(['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx']);
const IMAGE_EXT = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg']);
const TEXT_EXT = new Set([
  'txt',
  'json',
  'csv',
  'log',
  'xml',
  'yaml',
  'yml',
  'css',
  'js',
  'mjs',
  'cjs',
  'ts',
  'tsx',
  'jsx',
  'vue',
  'py',
  'sh',
  'bash',
  'sql',
  'ini',
  'toml',
  'conf',
  'cfg',
  'go',
  'rs',
  'java',
  'c',
  'cpp',
  'h',
  'dat',
  'properties',
  'dockerfile',
  'eml',
]);

function extensionFromFilename(filename: string): string {
  const base = filename.split('/').pop() ?? filename;
  const i = base.lastIndexOf('.');
  return i >= 0 ? base.slice(i + 1).toLowerCase() : '';
}

const IMAGE_MIME_BY_EXT: Record<string, string> = {
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  gif: 'image/gif',
  webp: 'image/webp',
  bmp: 'image/bmp',
  svg: 'image/svg+xml',
};

export function coerceBlobForPreview(blob: Blob, filename: string, kind: KnowledgeFilePreviewKind): Blob {
  if (kind === 'pdf') {
    if (blob.type === 'application/pdf' || blob.type === 'application/x-pdf') {
      return blob;
    }
    return new Blob([blob], { type: 'application/pdf' });
  }
  if (kind === 'image') {
    if (blob.type.startsWith('image/')) {
      return blob;
    }
    const ext = extensionFromFilename(filename);
    const mime = IMAGE_MIME_BY_EXT[ext];
    if (mime) {
      return new Blob([blob], { type: mime });
    }
    return blob;
  }
  if (kind === 'html') {
    if (blob.type === 'text/html' || blob.type === 'application/xhtml+xml') {
      return blob;
    }
    return new Blob([blob], { type: 'text/html' });
  }
  return blob;
}

export function getKnowledgeFilePreviewKind(filename: string): KnowledgeFilePreviewKind {
  const ext = extensionFromFilename(filename);
  if (OFFICE_ONLINE_EXTS.has(ext)) return 'office';
  if (IMAGE_EXT.has(ext)) return 'image';
  if (ext === 'pdf') return 'pdf';
  if (ext === 'md' || ext === 'markdown' || ext === 'mdx') return 'markdown';
  if (ext === 'html' || ext === 'htm') return 'html';
  if (ext === '' || TEXT_EXT.has(ext)) return 'text';
  return 'unsupported';
}
