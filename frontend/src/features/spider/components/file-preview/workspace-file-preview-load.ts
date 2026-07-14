import {
  coerceBlobForPreview,
  getKnowledgeFilePreviewKind,
  type KnowledgeFilePreviewKind,
} from '@/features/spider/components/file-preview/knowledge-preview';

export type WorkspaceFilePreviewLoadResult = {
  status: 'loaded';
  kind: KnowledgeFilePreviewKind;
  textContent: string;
  objectUrl: string | null;
  error: string | null;
};

export async function loadWorkspaceFilePreviewContent(params: {
  fileName: string;
  fetchBlob: () => Promise<Blob>;
  fetchText?: () => Promise<string>;
  loadFailedMessage: string;
}): Promise<WorkspaceFilePreviewLoadResult> {
  const { fileName, fetchBlob, fetchText, loadFailedMessage } = params;
  const kind = getKnowledgeFilePreviewKind(fileName);

  if (kind === 'unsupported' || kind === 'office') {
    return { status: 'loaded', kind, textContent: '', objectUrl: null, error: null };
  }

  try {
    if (kind === 'pdf') {
      const blob = await fetchBlob();
      const coerced = coerceBlobForPreview(blob, fileName, kind);
      const url = URL.createObjectURL(coerced);
      return { status: 'loaded', kind, textContent: '', objectUrl: url, error: null };
    }

    if (kind === 'image') {
      const blob = await fetchBlob();
      const url = URL.createObjectURL(coerceBlobForPreview(blob, fileName, kind));
      return { status: 'loaded', kind, textContent: '', objectUrl: url, error: null };
    }

    if (kind === 'html') {
      const blob = await fetchBlob();
      const url = URL.createObjectURL(coerceBlobForPreview(blob, fileName, kind));
      return { status: 'loaded', kind, textContent: '', objectUrl: url, error: null };
    }

    const text = fetchText ? await fetchText() : await (await fetchBlob()).text();
    return { status: 'loaded', kind, textContent: text, objectUrl: null, error: null };
  } catch (err) {
    console.error('loadWorkspaceFilePreviewContent failed:', err);
    return { status: 'loaded', kind, textContent: '', objectUrl: null, error: loadFailedMessage };
  }
}
