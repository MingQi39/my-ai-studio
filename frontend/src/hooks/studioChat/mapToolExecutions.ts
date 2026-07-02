import type { ChatToolRun } from '@/components/chat';
import type { StudioChatMessage } from '@/hooks/studioChat/types';
import type { ToolExecutionResponse } from '@/services/api';

function mapExecutionStatus(
  status: ToolExecutionResponse['status'],
): ChatToolRun['status'] {
  if (status === 'running' || status === 'pending') return 'running';
  if (status === 'failed') return 'error';
  return 'completed';
}

function mapExecutionToRun(ex: ToolExecutionResponse): ChatToolRun {
  return {
    tool_name: ex.tool_name,
    tool_type: ex.tool_type,
    tool_input: ex.input_params,
    tool_output: ex.output ?? undefined,
    status: mapExecutionStatus(ex.status),
  };
}

export function buildToolStateFromExecutions(
  executions: ToolExecutionResponse[] | null | undefined,
): Pick<StudioChatMessage, 'toolRuns' | 'tool'> {
  if (!executions?.length) return {};

  const toolRuns = executions.map(mapExecutionToRun);
  const pythonRun = toolRuns.find((run) => run.tool_name === 'execute_python');

  if (!pythonRun) {
    return { toolRuns };
  }

  return {
    toolRuns,
    tool: {
      name: pythonRun.tool_name,
      code: String(pythonRun.tool_input?.code ?? ''),
      output: pythonRun.tool_output,
      status: pythonRun.status === 'running' ? 'running' : 'completed',
    },
  };
}

export function hasRunningToolExecutions(
  executions: ToolExecutionResponse[] | null | undefined,
): boolean {
  return Boolean(
    executions?.some((ex) => ex.status === 'running' || ex.status === 'pending'),
  );
}
