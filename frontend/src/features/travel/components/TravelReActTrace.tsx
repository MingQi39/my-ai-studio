import { useState } from 'react';
import { Activity, ChevronDown, ChevronRight } from 'lucide-react';
import { ReActTimeline } from '@/features/travel/components/ReActTimeline';
import type { ReActStep } from '@/features/travel/types/react';

type TravelReActTraceProps = {
  steps: ReActStep[];
  isDarkMode?: boolean;
  defaultExpanded?: boolean;
};

export function TravelReActTrace({
  steps,
  isDarkMode = false,
  defaultExpanded = true,
}: TravelReActTraceProps) {
  const [showTrace, setShowTrace] = useState(defaultExpanded);

  if (steps.length === 0) return null;

  return (
    <div className="mb-3 w-full">
      <button
        type="button"
        onClick={() => setShowTrace(!showTrace)}
        className="flex items-center gap-2 px-3 py-1.5 bg-slate-50 hover:bg-slate-100 dark:bg-[#1E293B]/50 dark:hover:bg-[#1E293B] text-slate-600 dark:text-slate-300 rounded-full text-xs font-medium transition-colors border border-slate-200 dark:border-slate-700/50"
      >
        {showTrace ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <Activity size={14} className="text-[#3B82F6]" />
        🧠 思考过程 ({steps.length} 步)
      </button>

      {showTrace && (
        <div className="mt-3 mb-4 p-4 bg-slate-50 dark:bg-[#0F172A] border border-slate-200 dark:border-slate-800 rounded-xl text-xs w-full max-h-[60vh] overflow-y-auto scroll-smooth">
          <ReActTimeline steps={steps} isDarkMode={isDarkMode} />
        </div>
      )}
    </div>
  );
}
