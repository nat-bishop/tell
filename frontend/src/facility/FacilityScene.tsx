"use client";

import { useGameStore } from "@/hooks/useGameStore";
import { useFacilityContext } from "@/facility/FacilityProvider";
import { FacilityLobby } from "@/facility/phases/FacilityLobby";
import { FacilityMatchup } from "@/facility/phases/FacilityMatchup";
import { FacilityPrompt } from "@/facility/phases/FacilityPrompt";
import { FacilityGameOver } from "@/facility/phases/FacilityGameOver";
import { FacilityBrainTest } from "@/facility/phases/FacilityBrainTest";

export function FacilityScene() {
  const phase = useGameStore((s) => s.phase);
  const roundType = useGameStore((s) => s.roundType);
  const { transitionState } = useFacilityContext();

  if (transitionState === "lockdown" || transitionState === "reconfigure") return null;

  return (
    <>
      {phase === "lobby" && <FacilityLobby />}
      {phase === "prompt" && <FacilityPrompt />}
      {(phase === "active" || phase === "results") && (
        roundType === "task" ? <FacilityMatchup /> :
        roundType === "brain_test" ? <FacilityBrainTest /> : null
      )}
      {phase === "game_over" && <FacilityGameOver />}
    </>
  );
}
