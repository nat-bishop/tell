"use client";

import { useGameStore } from "@/hooks/useGameStore";
import { useFacilityContext } from "@/facility/FacilityProvider";
import { FacilityLobby } from "@/facility/phases/FacilityLobby";
import { FacilityPrompt } from "@/facility/phases/FacilityPrompt";
import { FacilityVote } from "@/facility/phases/FacilityVote";
import { FacilityVoteResults } from "@/facility/phases/FacilityVoteResults";
import { FacilityGameOver } from "@/facility/phases/FacilityGameOver";
import { FacilityBrainTest } from "@/facility/phases/FacilityBrainTest";
import { FacilityWager } from "@/facility/phases/FacilityWager";
import { FacilitySignalPrompt } from "@/facility/phases/FacilitySignalPrompt";
import { FacilitySignalActive } from "@/facility/phases/FacilitySignalActive";
import { FacilitySignalResults } from "@/facility/phases/FacilitySignalResults";

const MINIGAME_COMPONENTS: Record<string, { Active: React.FC; Results: React.FC; Prompt?: React.FC }> = {
  task: { Active: FacilityVote, Results: FacilityVoteResults },
  brain_test: { Active: FacilityBrainTest, Results: FacilityBrainTest },
  wager: { Active: FacilityWager, Results: FacilityWager },
  signal: { Active: FacilitySignalActive, Results: FacilitySignalResults, Prompt: FacilitySignalPrompt },
};

export function FacilityScene() {
  const phase = useGameStore((s) => s.phase);
  const roundType = useGameStore((s) => s.roundType);
  const { transitionState } = useFacilityContext();

  if (transitionState === "lockdown" || transitionState === "reconfigure") return null;

  const minigame = roundType ? MINIGAME_COMPONENTS[roundType] : null;

  return (
    <>
      {phase === "lobby" && <FacilityLobby />}
      {phase === "prompt" && (minigame?.Prompt ? <minigame.Prompt /> : <FacilityPrompt />)}
      {phase === "active" && minigame?.Active && <minigame.Active />}
      {phase === "results" && minigame?.Results && <minigame.Results />}
      {phase === "game_over" && <FacilityGameOver />}
    </>
  );
}
