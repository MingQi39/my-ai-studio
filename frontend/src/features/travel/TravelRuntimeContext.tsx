import { createContext, useContext } from 'react';

export interface TravelRuntimeContextValue {
  modelConfigId: string | null;
}

export const TravelRuntimeContext = createContext<TravelRuntimeContextValue>({
  modelConfigId: null,
});

export function useTravelRuntime() {
  return useContext(TravelRuntimeContext);
}
