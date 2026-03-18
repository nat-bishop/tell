"use client";

import { useEffect, useState, useRef } from "react";
import { useGameStore, type GamePhase } from "@/hooks/useGameStore";
import { FacilityTimer } from "@/facility/FacilityTimer";
import { FacilityNarration } from "@/facility/FacilityNarration";
import { HudPanel } from "@/facility/HudPanel";
import { useTimer } from "@/hooks/useTimer";
import { FacilityProvider, useFacilityContext } from "@/facility/FacilityProvider";
import { FacilityViewport } from "@/facility/FacilityViewport";
import { FacilityScene } from "@/facility/FacilityScene";
import { TransitionOverlay } from "@/facility/TransitionOverlay";
import { RiveScene } from "@/facility/RiveScene";
import { useFacilityCharacters } from "@/facility/useFacilityCharacters";

const INTERSTITIAL_PHASES = new Set<GamePhase>([
  "prompt", "brain_test", "brain_test_results", "matchup",
]);

const FALLBACK_DURATIONS: Partial<Record<GamePhase, number>> = {
  prompt: 45,
  brain_test: 12,
  brain_test_results: 15,
  matchup: 12,
};

function ColdOpen({ playerCount }: { playerCount: number }) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const timers = [
      setTimeout(() => setStep(1), 400),
      setTimeout(() => setStep(2), 3000),
    ];
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6">
      {step >= 0 && (
        <p className="animate-fade-in font-system text-[1.2rem] text-ink tracking-[0.2em] uppercase">
          {playerCount} SUBJECTS DETECTED
        </p>
      )}
      {step >= 1 && (
        <p className="animate-fade-in font-system text-[0.8rem] text-dim tracking-[0.15em] lowercase">
          some are not what they seem
        </p>
      )}
    </div>
  );
}

function FacilityInner() {
  const {
    phase, phaseDeadline, phaseDuration, players, actionStartsAt,
  } = useGameStore();
  const remaining = useTimer(phaseDeadline);
  const { rive, setRive, transitionState, startTransition, snapTo } = useFacilityContext();
  useFacilityCharacters(rive);

  // Cold open state -- show once when game transitions from lobby to first round
  const [showColdOpen, setShowColdOpen] = useState(false);
  const [coldOpenDone, setColdOpenDone] = useState(false);
  const prevPhaseForColdRef = useRef<GamePhase>("lobby");

  useEffect(() => {
    if (
      prevPhaseForColdRef.current === "lobby" &&
      phase !== "lobby" &&
      !coldOpenDone
    ) {
      setShowColdOpen(true);
      const timer = setTimeout(() => {
        setShowColdOpen(false);
        setColdOpenDone(true);
      }, 5500);
      return () => clearTimeout(timer);
    }
    prevPhaseForColdRef.current = phase;
  }, [phase, coldOpenDone]);

  // Transition interstitials -- drive the transition machine on phase changes
  const prevPhaseRef = useRef<GamePhase>(phase);
  const prevActionStartsAtRef = useRef<string | null>(actionStartsAt);

  useEffect(() => {
    const phaseChanged = prevPhaseRef.current !== phase;
    const isReconnection = !phaseChanged && actionStartsAt !== prevActionStartsAtRef.current;

    prevPhaseRef.current = phase;
    prevActionStartsAtRef.current = actionStartsAt;

    if (showColdOpen) return;

    if (!INTERSTITIAL_PHASES.has(phase) || !actionStartsAt) {
      return;
    }

    if (isReconnection) {
      // state_sync (reconnection) -- snap to idle
      snapTo();
      return;
    }

    if (phaseChanged) {
      const holdMs = new Date(actionStartsAt).getTime() - Date.now();
      if (holdMs <= 0) {
        snapTo();
        return;
      }
      startTransition(holdMs);
    }
  }, [phase, actionStartsAt, showColdOpen, startTransition, snapTo]);

  const total = phaseDuration ?? FALLBACK_DURATIONS[phase] ?? 0;
  const hideTimer = phase === "lobby" || phase === "game_over" || showColdOpen || transitionState !== "idle";

  return (
    <FacilityViewport>
      <RiveScene onRiveReady={setRive} />
      {!hideTimer && <FacilityTimer remaining={remaining} total={total} />}
      <HudPanel />
      <FacilityNarration />
      <TransitionOverlay />
      {showColdOpen ? (
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <ColdOpen playerCount={players.length} />
        </div>
      ) : (
        <FacilityScene />
      )}
    </FacilityViewport>
  );
}

export function FacilityGameContent() {
  return (
    <FacilityProvider>
      <FacilityInner />
    </FacilityProvider>
  );
}
