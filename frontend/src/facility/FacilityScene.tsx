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

const STEP_COMPONENTS: Record<string, React.FC> = {
  "compose": FacilityPrompt,
  "signal_compose": FacilitySignalPrompt,
  "vote": FacilityVote,
  "vote_results": FacilityVoteResults,
  "brain_test": FacilityBrainTest,
  "brain_test_results": FacilityBrainTest,
  "wager": FacilityWager,
  "wager_results": FacilityWager,
  "signal_guess": FacilitySignalActive,
  "signal_results": FacilitySignalResults,
};

export function FacilityScene() {
  const phase = useGameStore((s) => s.phase);
  const component = useGameStore((s) => s.component);
  const { transitionState } = useFacilityContext();

  if (transitionState === "lockdown" || transitionState === "reconfigure") return null;

  // Lobby and game_over route by phase
  if (phase === "lobby") return <FacilityLobby />;
  if (phase === "game_over") return <FacilityGameOver />;

  // During round phase, route by component key
  if (phase === "round" && component) {
    const StepComponent = STEP_COMPONENTS[component];
    if (StepComponent) return <StepComponent />;
  }

  return null;
}
