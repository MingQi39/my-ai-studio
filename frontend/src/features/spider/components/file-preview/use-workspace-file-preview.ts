import { useCallback, useState } from 'react';

import { getKnowledgeFilePreviewKind, type KnowledgeFilePreviewKind } from '@/features/spider/components/file-preview/knowledge-preview';
import { loadWorkspaceFilePreviewContent } from '@/features/spider/components/file-preview/workspace-file-preview-load';

export type OpenWorkspaceFilePreviewParams = {
  title: string;
  fileName: string;
  fetchBlob: () => Promise<Blob>;
  fetchText?: () => Promise<string>;
  loadFailedMessage: string;
  previewDescription?: string;
  unsupportedMessage?: string;
  onDownloadWhenUnsupported?: () => void | Promise<void>;
};

export function useWorkspaceFilePreview() {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [title, setTitle] = useState('');
  const [kind, setKind] = useState<KnowledgeFilePreviewKind>('unsupported');
  const [textContent, setTextContent] = useState('');
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [onDownloadWhenUnsupported, setOnDownloadWhenUnsupported] = useState<
    (() => void | Promise<void>) | undefined
  >();
  const [previewDescription, setPreviewDescription] = useState('');
  const [unsupportedMessage, setUnsupportedMessage] = useState<string | undefined>(undefined);

  const revokeObjectUrl = useCallback((url: string | null) => {
    if (url?.startsWith('blob:')) URL.revokeObjectURL(url);
  }, []);

  const close = useCallback(() => {
    setOpen(false);
    setLoading(false);
    setTextContent('');
    setError(null);
    setOnDownloadWhenUnsupported(undefined);
    setPreviewDescription('');
    setUnsupportedMessage(undefined);
    setObjectUrl((prev) => {
      revokeObjectUrl(prev);
      return null;
    });
  }, [revokeObjectUrl]);

  const openPreview = useCallback(
    async (params: OpenWorkspaceFilePreviewParams) => {
      const {
        title: previewTitle,
        fileName,
        fetchBlob,
        fetchText,
        loadFailedMessage,
        previewDescription: previewDesc,
        unsupportedMessage: unsupMsg,
        onDownloadWhenUnsupported: onDl,
      } = params;

      const nextKind = getKnowledgeFilePreviewKind(fileName);
      setTitle(previewTitle);
      setPreviewDescription(previewDesc ?? '');
      setUnsupportedMessage(unsupMsg);
      setKind(nextKind);
      setOpen(true);
      setLoading(true);
      setTextContent('');
      setError(null);
      setOnDownloadWhenUnsupported(() => onDl ?? undefined);
      setObjectUrl((prev) => {
        revokeObjectUrl(prev);
        return null;
      });

      const result = await loadWorkspaceFilePreviewContent({
        fileName,
        fetchBlob,
        fetchText,
        loadFailedMessage,
      });

      setKind(result.kind);
      setTextContent(result.textContent);
      setObjectUrl(result.objectUrl);
      setError(result.error);
      setLoading(false);
    },
    [revokeObjectUrl],
  );

  return {
    open,
    loading,
    title,
    kind,
    textContent,
    objectUrl,
    error,
    onDownloadWhenUnsupported,
    previewDescription,
    unsupportedMessage,
    openPreview,
    close,
  };
}
