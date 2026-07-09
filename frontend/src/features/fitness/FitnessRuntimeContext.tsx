import { createContext, useContext } from 'react';

export interface FitnessRuntimeContextValue {
  modelConfigId: string | null;
}

export const FitnessRuntimeContext = createContext<FitnessRuntimeContextValue>({
  modelConfigId: null,
});

export function useFitnessRuntime() {
  return useContext(FitnessRuntimeContext);
}

