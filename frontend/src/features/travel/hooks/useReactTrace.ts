/**
 * ReAct 追踪 Hook — /api/v1/travel/agent/run
 */

import { useReactStore, type ToolCall } from '@/features/travel/stores/useReactStore';
import { SSEClient } from '@/features/travel/services/sse/SSEClient';
import type { SSEEvent } from '@/features/travel/types/events';
import { TRAVEL_API_BASE, travelHeaders } from '@/features/travel/services/api/client';
import { useTravelRuntime } from '@/features/travel/TravelRuntimeContext';

export function useReactTrace() {
  const { addStep, setSimulationState, setStats, setError, reset } = useReactStore();
  const { modelConfigId } = useTravelRuntime();

  const startTrace = async (message: string, maxRounds: number) => {
    if (!modelConfigId) {
      setError('请先在设置中配置模型连接');
      return;
    }

    reset();
    setSimulationState('loading');

    const pendingToolCalls: Map<string, ToolCall> = new Map();

    const client = new SSEClient({
      url: `${TRAVEL_API_BASE}/travel/agent/run`,
      method: 'POST',
      headers: travelHeaders(),
      body: JSON.stringify({
        message,
        max_rounds: maxRounds,
        model_config_id: modelConfigId,
      }),
      onEvent: (event: SSEEvent) => {
        if (event.type === 'tool_call_start') {
          pendingToolCalls.set(event.call_id, {
            id: event.call_id,
            tool_name: event.tool_name,
            tool_args: event.tool_args,
            status: 'pending',
          });
        }

        if (event.type === 'tool_call_result') {
          const toolCall = pendingToolCalls.get(event.call_id);
          if (toolCall) {
            toolCall.result = event.result;
            toolCall.status = event.status;
            toolCall.duration_ms = event.duration_ms;
            toolCall.error = event.error;
          }
        }

        if (event.type === 'step' && event.step_type && event.content) {
          if (event.step_type === 'Act') {
            const completedToolCalls = Array.from(pendingToolCalls.values()).filter(
              (tc) => tc.status !== 'pending',
            );
            addStep({
              type: event.step_type,
              content: event.content,
              round: event.round || 0,
              sequence: event.sequence || 0,
              toolCalls: completedToolCalls,
            });
            pendingToolCalls.clear();
          } else {
            addStep({
              type: event.step_type,
              content: event.content,
              round: event.round || 0,
              sequence: event.sequence || 0,
            });
          }
        }

        if (event.type === 'done') {
          if (event.stats) setStats(event.stats);
          setSimulationState('done');
          pendingToolCalls.clear();
        }

        if (event.type === 'error') {
          setError(event.message || '未知错误');
          pendingToolCalls.clear();
        }
      },
      onError: (error) => setError(`连接错误: ${error.message}`),
      onComplete: () => {
        if (useReactStore.getState().simulationState === 'loading') {
          setSimulationState('done');
        }
      },
    });

    await client.start();
  };

  return { startTrace };
}
