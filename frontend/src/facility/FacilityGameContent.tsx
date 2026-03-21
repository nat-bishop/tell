"use client";

import { useEffect, useState, useRef } from "react";
import { useGameStore, type GamePhase } from "@/hooks/useGameStore";
import { FacilityTimer } from "@/facility/FacilityTimer";
import { FacilityNarration } from "@/facility/FacilityNarration";
import { HudPanel } from "@/facility/HudPanel";
import { useTimer } from "@/hooks/useTimer";
import { FacilityProvider, useFacilityContext } from "@/facility/FacilityProvider";
import { FacilityScene } from "@/facility/FacilityScene";
import { TransitionOverlay } from "@/facility/TransitionOverlay";
import { FacilityBackground } from "@/facility/FacilityBackground";

const FALLBACK_DURATIONS: Partial<Record<string, number>> = {
  compose: 60,
  vote: 35,
  results: 15,
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
    phase, phaseDeadline, phaseDuration, players,
    roundNumber, component, stepName,
  } = useGameStore();
  const remaining = useTimer(phaseDeadline);
  const { transitionState, startTransition, snapTo } = useFacilityContext();

  // Cold open state -- show once when game transitions from lobby to first round
  const [showColdOpen, setShowColdOpen] = useState(false);
  const [coldOpenDone, setColdOpenDone] = useState(false);
  const prevPhaseForColdRef = useRef<GamePhase>(phase);

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

  // Transition logic — driven by step changes
  const prevRoundRef = useRef(roundNumber);
  const prevComponentRef = useRef(component);
  const prevStepNameRef = useRef(stepName);

  useEffect(() => {
    const prevRound = prevRoundRef.current;
    const prevComponent = prevComponentRef.current;
    const prevStep = prevStepNameRef.current;

    prevRoundRef.current = roundNumber;
    prevComponentRef.current = component;
    prevStepNameRef.current = stepName;

    if (showColdOpen) return;
    if (phase === "lobby" || phase === "game_over") return;

    // Reconnection: if step didn't actually change, snap
    if (prevStep === stepName && prevRound === roundNumber) {
      return;
    }

    // Determine transition duration based on what changed
    let transitionMs = 0;
    if (roundNumber !== prevRound) {
      transitionMs = 4000; // new round: full overlay
    } else if (component !== prevComponent) {
      transitionMs = 700; // new component: brief fade
    }
    // same component: instant swap (transitionMs = 0)

    if (transitionMs > 0) {
      startTransition(transitionMs);
    } else {
      snapTo();
    }
  }, [phase, roundNumber, component, stepName, showColdOpen, startTransition, snapTo]);

  const total = phaseDuration ?? FALLBACK_DURATIONS[stepName ?? ""] ?? 0;
  const hideTimer = phase === "lobby" || phase === "game_over" || showColdOpen || transitionState !== "idle" || (component ?? "").endsWith("_results");

  return (
    <div className="facility-viewport">
      <div className="facility-vignette" />
      <div style={{ position: "relative", zIndex: 10, width: "100%", height: "100%" }}>
        <FacilityBackground />
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
      </div>
    </div>
  );
}

export function FacilityGameContent() {
  return (
    <FacilityProvider>
      <FacilityInner />
    </FacilityProvider>
  );
}
