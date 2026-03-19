import { useMemo } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { getPhaseLayout } from "./phaseLayouts";

export function usePhaseLayout() {
  const phase = useGameStore((s) => s.phase);
  const roundType = useGameStore((s) => s.roundType);
  return useMemo(() => getPhaseLayout(phase, roundType), [phase, roundType]);
}
