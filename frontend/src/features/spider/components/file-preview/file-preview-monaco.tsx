import Editor, { loader } from '@monaco-editor/react';
import * as monaco from 'monaco-editor';

import { getLanguageFromPath } from '@/features/spider/components/file-preview/language-utils';

loader.config({ monaco });

interface FilePreviewMonacoProps {
  fileName: string;
  value: string;
  isDarkMode?: boolean;
}

export function FilePreviewMonaco({ fileName, value, isDarkMode = false }: FilePreviewMonacoProps) {
  const theme = isDarkMode ? 'vs-dark' : 'vs';

  return (
    <Editor
      height="100%"
      language={getLanguageFromPath(fileName)}
      value={value}
      theme={theme}
      path={fileName}
      options={{
        readOnly: true,
        fontSize: 13,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        wordWrap: 'on',
        automaticLayout: true,
      }}
    />
  );
}
