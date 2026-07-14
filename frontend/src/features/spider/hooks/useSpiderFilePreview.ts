import { useCallback, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';

import { useWorkspaceFilePreview } from '@/features/spider/components/file-preview/use-workspace-file-preview';
import {
  downloadSpiderWorkspaceFile,
  fetchSpiderWorkspaceFileBlob,
  fetchSpiderWorkspaceFileText,
} from '@/features/spider/services/api/spider';

export function useSpiderFilePreview(sessionId: string | null) {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedFile = searchParams.get('file');
  const lastLoadedKeyRef = useRef<string | null>(null);

  const {
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
  } = useWorkspaceFilePreview();

  const selectFile = useCallback(
    (fileName: string) => {
      setSearchParams({ file: fileName }, { replace: false });
    },
    [setSearchParams],
  );

  useEffect(() => {
    if (!sessionId || !selectedFile) {
      lastLoadedKeyRef.current = null;
      close();
      return;
    }

    const loadKey = `${sessionId}:${selectedFile}`;
    if (lastLoadedKeyRef.current === loadKey) return;
    lastLoadedKeyRef.current = loadKey;

    void openPreview({
      title: selectedFile,
      fileName: selectedFile,
      fetchBlob: () => fetchSpiderWorkspaceFileBlob(sessionId, selectedFile, { forPreview: true }),
      fetchText: () => fetchSpiderWorkspaceFileText(sessionId, selectedFile),
      loadFailedMessage: t('spider.files.loadFailed'),
      previewDescription: t('spider.files.previewDescription', { name: selectedFile }),
      unsupportedMessage: t('spider.files.unsupported'),
      onDownloadWhenUnsupported: async () => {
        try {
          await downloadSpiderWorkspaceFile(sessionId, selectedFile);
          toast.success(t('spider.files.downloaded', { name: selectedFile }));
        } catch (err) {
          console.error('Download spider workspace file failed:', err);
          toast.error(t('spider.files.downloadFailed'));
        }
      },
    });
  }, [sessionId, selectedFile, openPreview, close, t]);

  return {
    selectedFile,
    selectFile,
    previewOpen: open,
    previewLoading: loading,
    previewTitle: title,
    previewKind: kind,
    previewText: textContent,
    previewObjectUrl: objectUrl,
    previewError: error,
    previewOnDownloadUnsupported: onDownloadWhenUnsupported,
    previewDescription,
    previewUnsupportedMessage: unsupportedMessage,
  };
}
