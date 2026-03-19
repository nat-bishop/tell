"use client";

import { useGameStore } from "@/hooks/useGameStore";
import { useFacilityContext } from "@/facility/FacilityProvider";
import { FacilityLobby } from "@/facility/phases/FacilityLobby";
import { FacilityPrompt } from "@/facility/phases/FacilityPrompt";
import { FacilityVote } from "@/facility/phases/FacilityVote";
import { FacilityVoteResults } from "@/facility/phases/FacilityVoteResults";
import { FacilityGameOver } from "@/facility/phases/FacilityGameOver";
import { FacilityBrainTest } from "@/facility/phases/FacilityBrainTest";

export function FacilityScene() {
  const phase = useGameStore((s) => s.phase);
  const { transitionState } = useFacilityContext();

  if (transitionState === "lockdown" || transitionState === "reconfigure") return null;

  return (
    <>
      {phase === "lobby" && <FacilityLobby />}
      {phase === "prompt" && <FacilityPrompt />}
      {phase === "vote" && <FacilityVote />}
      {phase === "vote_results" && <FacilityVoteResults />}
      {(phase === "brain_test" || phase === "brain_test_results") && <FacilityBrainTest />}
      {phase === "game_over" && <FacilityGameOver />}
    </>
  );
}
