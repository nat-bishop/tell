import { useMemo } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { getPhaseLayout } from "./phaseLayouts";

export function usePhaseLayout() {
  const phase = useGameStore((s) => s.phase);
  const component = useGameStore((s) => s.component);
  return useMemo(() => getPhaseLayout(phase, component), [phase, component]);
}
