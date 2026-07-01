import {
  Activity,
  CheckCircle2,
  Code2,
  Lightbulb,
  Search,
} from 'lucide-react';

export type ReactStepType = 'Observe' | 'Think' | 'Act' | 'Verify' | string;

export function getReactStepIcon(type: ReactStepType) {
  switch (type) {
    case 'Observe':
      return <Search size={14} />;
    case 'Think':
      return <Lightbulb size={14} />;
    case 'Act':
      return <Code2 size={14} />;
    case 'Verify':
      return <CheckCircle2 size={14} />;
    default:
      return <Activity size={14} />;
  }
}

export function getReactStepColor(type: ReactStepType) {
  switch (type) {
    case 'Observe':
      return 'blue';
    case 'Think':
      return 'purple';
    case 'Act':
      return 'orange';
    case 'Verify':
      return 'green';
    default:
      return 'blue';
  }
}

export function getReactStepLabel(type: ReactStepType) {
  const labels: Record<string, string> = {
    Observe: '观察环境 (Observe)',
    Think: '思考决策 (Think)',
    Act: '执行动作 (Act)',
    Verify: '观察结果 (Verify)',
  };
  return labels[type] || type;
}
