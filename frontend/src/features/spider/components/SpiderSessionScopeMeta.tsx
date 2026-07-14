import React from 'react';
import { useTranslation } from 'react-i18next';

interface SpiderSessionScopeMetaProps {
  sessionId: string | null;
  title: string | null;
  targetUrl: string | null;
  className?: string;
  indentClassName?: string;
}

/** Shared session scope label used by files workspace and control panel. */
export function SpiderSessionScopeMeta({
  sessionId,
  title,
  targetUrl,
  className,
  indentClassName = '',
}: SpiderSessionScopeMetaProps) {
  const { t } = useTranslation();

  if (!sessionId) return null;

  const sessionLabel = t('spider.files.sessionScope', {
    title: title || t('spider.files.unnamedSession'),
  });

  return (
    <div className={className}>
      <p className={`truncate text-[11px] text-[var(--text-secondary)] ${indentClassName}`} title={sessionLabel}>
        {sessionLabel}
      </p>
      {targetUrl ? (
        <p
          className={`truncate text-[11px] text-[var(--text-secondary)]/80 ${indentClassName}`}
          title={targetUrl}
        >
          {targetUrl}
        </p>
      ) : null}
    </div>
  );
}
