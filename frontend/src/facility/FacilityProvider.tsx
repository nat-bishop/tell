"use client";

import { createContext, useContext, useState, useCallback } from "react";
import { useTransitionMachine, type TransitionState } from "@/facility/useTransitionMachine";

interface FacilityContextValue {
  rive: any | null;
  setRive: (rive: any) => void;
  transitionState: TransitionState;
  startTransition: (holdMs: number) => void;
  snapTo: () => void;
}

const FacilityContext = createContext<FacilityContextValue | null>(null);

export function FacilityProvider({ children }: { children: React.ReactNode }) {
  const [rive, setRiveState] = useState<any | null>(null);
  const { transitionState, startTransition, snapTo } = useTransitionMachine();
  const setRive = useCallback((instance: any) => setRiveState(instance), []);

  return (
    <FacilityContext.Provider value={{ rive, setRive, transitionState, startTransition, snapTo }}>
      {children}
    </FacilityContext.Provider>
  );
}

export function useFacilityContext(): FacilityContextValue {
  const ctx = useContext(FacilityContext);
  if (!ctx) throw new Error("useFacilityContext must be used within FacilityProvider");
  return ctx;
}
