import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Bell, Loader2 } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { PUSH_FREQUENCY_OPTIONS } from '@/hooks/useInterviewPush';

const ROLE_OPTIONS = ['前端', '全栈', '后端', 'AI 应用工程'] as const;
const DIFFICULTY_OPTIONS: { label: string; desc: string }[] = [
  { label: '初级', desc: '定位与基础表达' },
  { label: '中级', desc: '机制与取舍' },
  { label: '高级', desc: '工程证据与风险' },
];
const SALARY_OPTIONS = ['15-25k', '25-40k', '40-60k', '60k+'] as const;

function ChoiceGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="text-sm font-medium text-[var(--text-primary)]">{label}</p>
      <div className="mt-3 flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

function ChoiceButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg px-3 py-1.5 text-sm transition ${
        active
          ? 'bg-[var(--text-primary)] text-[var(--bg-card)]'
          : 'border border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
      }`}
    >
      {children}
    </button>
  );
}

export type InterviewSettingsSheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  targetRole: string;
  customRole: string;
  difficulty: string;
  salaryBand: string;
  onTargetRole: (role: string) => void;
  onCustomRole: (v: string) => void;
  onDifficulty: (d: string) => void;
  onSalaryBand: (b: string) => void;
  onApplyGoal: () => void;
  applyGoalDisabled?: boolean;
  targetDeadline: string;
  onTargetDeadline: (v: string) => void;
  onApplyDeadline: () => void;
  applyDeadlineDisabled?: boolean;
  supportsPush: boolean;
  pushEnabled: boolean;
  pushFrequency: string;
  pushTime: string;
  pushSettingsBusy?: boolean;
  onPushEnabled: (v: boolean) => void;
  onPushFrequency: (v: string) => void;
  onPushTime: (v: string) => void;
  onPushNow: () => void;
  pushNowBusy?: boolean;
};

export function InterviewSettingsSheet({
  open,
  onOpenChange,
  targetRole,
  customRole,
  difficulty,
  salaryBand,
  onTargetRole,
  onCustomRole,
  onDifficulty,
  onSalaryBand,
  onApplyGoal,
  applyGoalDisabled,
  targetDeadline,
  onTargetDeadline,
  onApplyDeadline,
  applyDeadlineDisabled,
  supportsPush,
  pushEnabled,
  pushFrequency,
  pushTime,
  pushSettingsBusy,
  onPushEnabled,
  onPushFrequency,
  onPushTime,
  onPushNow,
  pushNowBusy,
}: InterviewSettingsSheetProps) {
  const { t } = useTranslation();
  const resolvedDraft = (customRole.trim() || targetRole).trim();

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="flex w-full flex-col gap-0 overflow-y-auto bg-[var(--bg-card)] p-0 sm:max-w-md"
      >
        <SheetHeader className="border-b border-[var(--border-color)] p-4 text-left">
          <SheetTitle className="text-[var(--text-primary)]">{t('interviewNav.settings')}</SheetTitle>
          <SheetDescription className="text-[var(--text-secondary)]">
            {t('interviewNav.settingsHint')}
          </SheetDescription>
        </SheetHeader>

        <div className="flex flex-1 flex-col gap-8 p-4">
          <ChoiceGroup label={t('interviewNav.targetRole')}>
            {ROLE_OPTIONS.map((role) => (
              <ChoiceButton
                key={role}
                active={!customRole && targetRole === role}
                onClick={() => {
                  onCustomRole('');
                  onTargetRole(role);
                }}
              >
                {role}
              </ChoiceButton>
            ))}
          </ChoiceGroup>
          <input
            value={customRole}
            onChange={(e) => onCustomRole(e.target.value)}
            placeholder={t('interviewNav.customRolePlaceholder')}
            className="w-full rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] px-4 py-3 text-sm text-[var(--text-primary)] outline-none focus:border-amber-500/50"
          />

          <ChoiceGroup label={t('interviewNav.difficulty')}>
            {DIFFICULTY_OPTIONS.map((opt) => (
              <ChoiceButton
                key={opt.label}
                active={difficulty === opt.label}
                onClick={() => onDifficulty(opt.label)}
              >
                {opt.label}
                <span className="ml-1 opacity-60">· {opt.desc}</span>
              </ChoiceButton>
            ))}
          </ChoiceGroup>

          <ChoiceGroup label={t('interviewNav.salary')}>
            {SALARY_OPTIONS.map((band) => (
              <ChoiceButton
                key={band}
                active={salaryBand === band}
                onClick={() => onSalaryBand(band)}
              >
                {band}
              </ChoiceButton>
            ))}
          </ChoiceGroup>

          <div>
            <p className="text-sm font-medium text-[var(--text-primary)]">
              {t('interviewNav.deadline')}
            </p>
            <input
              type="date"
              value={targetDeadline}
              min={new Date().toISOString().slice(0, 10)}
              onChange={(e) => onTargetDeadline(e.target.value)}
              className="mt-3 w-full rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] px-4 py-3 text-sm text-[var(--text-primary)] outline-none focus:border-amber-500/50"
            />
            <p className="mt-2 text-[11px] text-[var(--text-secondary)]">
              {t('interviewNav.deadlineHint')}
            </p>
            <button
              type="button"
              disabled={applyDeadlineDisabled}
              onClick={onApplyDeadline}
              className="mt-3 w-full rounded-xl border border-[var(--border-color)] px-4 py-2.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-hover)] disabled:opacity-50"
            >
              {t('interviewNav.applyDeadline')}
            </button>
          </div>

          {supportsPush ? (
            <div>
              <p className="text-sm font-medium text-[var(--text-primary)]">
                {t('interviewNav.reminder')}
              </p>
              <label className="mt-3 flex items-center gap-2 text-sm text-[var(--text-primary)]">
                <input
                  type="checkbox"
                  checked={pushEnabled}
                  disabled={pushSettingsBusy}
                  onChange={(e) => onPushEnabled(e.target.checked)}
                  className="rounded border-[var(--border-color)]"
                />
                {t('interviewNav.enableDesktopReminder')}
              </label>
              <select
                value={pushFrequency}
                disabled={pushSettingsBusy}
                onChange={(e) => onPushFrequency(e.target.value)}
                className="mt-3 w-full rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] px-4 py-3 text-sm text-[var(--text-primary)] outline-none focus:border-amber-500/50 disabled:opacity-50"
              >
                {PUSH_FREQUENCY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <input
                type="time"
                value={pushTime}
                disabled={pushSettingsBusy}
                onChange={(e) => onPushTime(e.target.value)}
                className="mt-3 w-full rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] px-4 py-3 text-sm text-[var(--text-primary)] outline-none focus:border-amber-500/50 disabled:opacity-50"
              />
              <button
                type="button"
                disabled={pushNowBusy || !targetDeadline}
                onClick={onPushNow}
                className="mt-3 inline-flex w-full items-center justify-center gap-1.5 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-2.5 text-sm font-medium text-amber-900 hover:bg-amber-500/20 disabled:opacity-50 dark:text-amber-100"
              >
                {pushNowBusy ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Bell className="h-4 w-4" />
                )}
                {t('interviewNav.pushNow')}
              </button>
            </div>
          ) : null}
        </div>

        <SheetFooter className="border-t border-[var(--border-color)] p-4">
          <button
            type="button"
            disabled={applyGoalDisabled || !resolvedDraft || !salaryBand}
            onClick={onApplyGoal}
            className="w-full rounded-xl bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            {t('interviewNav.applyGoal')}
          </button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
