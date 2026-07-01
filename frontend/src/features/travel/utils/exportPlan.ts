import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { branding } from '@/features/travel/config/branding';
import type { Message } from '@/features/travel/stores/useChatStore';
import { printHtmlContent } from '@/features/travel/utils/printHtml';

export interface PlanExportOptions {
  includeThinking?: boolean;
  title?: string;
}

export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function buildPlanMarkdown(
  messages: Message[],
  options: PlanExportOptions = {},
): string {
  const { includeThinking = false, title } = options;
  const planTitle = title || branding.appSubtitle || '旅行规划';
  const exportedAt = new Date().toLocaleString('zh-CN');

  const lines: string[] = [
    `# ${planTitle}`,
    '',
    `> 导出时间：${exportedAt}`,
    '',
  ];

  for (const msg of messages) {
    if (msg.role === 'user') {
      lines.push('## 出行需求', '', msg.content.trim(), '');
      continue;
    }

    if (!msg.content.trim()) continue;

    const modeLabel = msg.mode === 'agent' ? 'Agent 规划方案' : 'LLM 回复';
    lines.push(`## ${modeLabel}`, '', msg.content.trim(), '');

    if (includeThinking && msg.thinkingSteps?.length) {
      lines.push('### 思考过程', '');
      for (const step of msg.thinkingSteps) {
        lines.push(`#### ${step.type}`, '', step.content.trim(), '');
      }
    }
  }

  lines.push('---', '', '*由 AI 生成，出行前请核实交通、票价与开放时间。*');
  return lines.join('\n');
}

export function buildLatestPlanMarkdown(messages: Message[]): string | null {
  const assistantMessages = messages.filter(
    (msg) => msg.role === 'assistant' && msg.content.trim(),
  );
  if (assistantMessages.length === 0) return null;

  const latest = assistantMessages[assistantMessages.length - 1];
  const userMessages = messages.filter((msg) => msg.role === 'user');
  const relatedUser = userMessages[userMessages.length - 1];

  const sections: string[] = [
    `# ${branding.appSubtitle || '旅行规划'}`,
    '',
    `> 导出时间：${new Date().toLocaleString('zh-CN')}`,
    '',
  ];

  if (relatedUser?.content.trim()) {
    sections.push('## 出行需求', '', relatedUser.content.trim(), '');
  }

  const modeLabel = latest.mode === 'agent' ? 'Agent 规划方案' : 'LLM 回复';
  sections.push(`## ${modeLabel}`, '', latest.content.trim(), '');
  sections.push('---', '', '*由 AI 生成，出行前请核实交通、票价与开放时间。*');

  return sections.join('\n');
}

export function sanitizeFilename(name: string): string {
  return name.replace(/[\\/:*?"<>|]/g, '-').replace(/\s+/g, '-').slice(0, 60) || 'travel-plan';
}

export function derivePlanFilename(messages: Message[]): string {
  const firstUser = messages.find((msg) => msg.role === 'user');
  const base = firstUser?.content.slice(0, 30) || 'travel-plan';
  const date = new Date().toISOString().slice(0, 10);
  return `${sanitizeFilename(base)}-${date}.md`;
}

export function downloadMarkdownFile(content: string, filename: string): void {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function copyTextToClipboard(text: string): Promise<void> {
  await navigator.clipboard.writeText(text);
}

export function markdownToHtml(markdown: string): string {
  return renderToStaticMarkup(
    React.createElement(
      ReactMarkdown,
      { remarkPlugins: [remarkGfm] },
      markdown,
    ),
  );
}

export const MARKDOWN_DOCUMENT_STYLES = `
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
    color: #0f172a;
    line-height: 1.7;
    margin: 0;
    background: #ffffff;
  }
  .markdown-body {
    max-width: 780px;
    margin: 0 auto;
    padding: 32px 24px 48px;
  }
  .markdown-body h1 {
    font-size: 1.75rem;
    font-weight: 700;
    margin: 0 0 0.75rem;
    line-height: 1.3;
  }
  .markdown-body h2 {
    font-size: 1.25rem;
    font-weight: 700;
    margin: 1.75rem 0 0.75rem;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 0.35rem;
  }
  .markdown-body h3,
  .markdown-body h4 {
    font-size: 1rem;
    font-weight: 700;
    margin: 1.25rem 0 0.5rem;
    color: #1d4ed8;
  }
  .markdown-body p { margin: 0.5rem 0; }
  .markdown-body strong { font-weight: 700; color: #0f172a; }
  .markdown-body em { color: #64748b; font-style: italic; }
  .markdown-body a {
    color: #2563eb;
    text-decoration: underline;
    word-break: break-all;
  }
  .markdown-body blockquote {
    margin: 0 0 1.5rem;
    padding: 0.5rem 1rem;
    border-left: 3px solid #3b82f6;
    background: #f8fafc;
    color: #64748b;
    font-size: 0.9rem;
  }
  .markdown-body ul,
  .markdown-body ol {
    margin: 0.5rem 0;
    padding-left: 1.5rem;
  }
  .markdown-body li { margin: 0.35rem 0; }
  .markdown-body li > ul,
  .markdown-body li > ol { margin: 0.25rem 0; }
  .markdown-body table {
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
    font-size: 0.9rem;
    background: #ffffff;
  }
  .markdown-body th,
  .markdown-body td {
    border: 1px solid #e2e8f0;
    padding: 0.5rem 0.75rem;
    text-align: left;
    vertical-align: top;
  }
  .markdown-body th {
    background: #f1f5f9;
    font-weight: 700;
  }
  .markdown-body hr {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 2rem 0;
  }
  .markdown-body code {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.85em;
    background: #f1f5f9;
    padding: 0.1em 0.35em;
    border-radius: 4px;
  }
  .markdown-body pre {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    overflow-x: auto;
  }
  .markdown-body pre code {
    background: transparent;
    padding: 0;
  }
  @media print {
    .markdown-body { padding: 0; }
  }
`;

export function buildMarkdownDocumentHtml(markdown: string, documentTitle: string): string {
  const bodyHtml = markdownToHtml(markdown);
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(documentTitle)}</title>
  <style>${MARKDOWN_DOCUMENT_STYLES}</style>
</head>
<body>
  <div class="markdown-body">${bodyHtml}</div>
</body>
</html>`;
}

export function printPlanDocument(markdown: string, documentTitle: string): void {
  printHtmlContent(buildMarkdownDocumentHtml(markdown, documentTitle));
}
