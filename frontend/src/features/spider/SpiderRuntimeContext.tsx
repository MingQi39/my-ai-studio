import { createContext, useContext } from 'react';

interface SpiderRuntimeContextValue {
  modelConfigId: string | null;
}

export const SpiderRuntimeContext = createContext<SpiderRuntimeContextValue>({
  modelConfigId: null,
});

export function useSpiderRuntime() {
  return useContext(SpiderRuntimeContext);
}
