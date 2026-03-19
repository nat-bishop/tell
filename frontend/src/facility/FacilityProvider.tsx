"use client";

import { createContext, useContext } from "react";
import { useTransitionMachine, type TransitionState } from "@/facility/useTransitionMachine";

interface FacilityContextValue {
  transitionState: TransitionState;
  startTransition: (holdMs: number) => void;
  snapTo: () => void;
}

const FacilityContext = createContext<FacilityContextValue | null>(null);

export function FacilityProvider({ children }: { children: React.ReactNode }) {
  const { transitionState, startTransition, snapTo } = useTransitionMachine();

  return (
    <FacilityContext.Provider value={{ transitionState, startTransition, snapTo }}>
      {children}
    </FacilityContext.Provider>
  );
}

export function useFacilityContext(): FacilityContextValue {
  const ctx = useContext(FacilityContext);
  if (!ctx) throw new Error("useFacilityContext must be used within FacilityProvider");
  return ctx;
}
