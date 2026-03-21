"use client";

import { useEffect, useRef } from "react";
import { useGameStore } from "@/hooks/useGameStore";
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

function FacilityInner() {
  const {
    phase, phaseDeadline, phaseDuration,
    roundNumber, component, stepName, timersDisabled,
  } = useGameStore();
  const remaining = useTimer(phaseDeadline);
  const { transitionState, startTransition, snapTo } = useFacilityContext();

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

    if (phase === "lobby" || phase === "game_over") return;

    // Reconnection: if step didn't actually change, snap
    if (prevStep === stepName && prevRound === roundNumber) {
      return;
    }

    // Determine transition duration based on what changed
    let transitionMs = 0;
    if (roundNumber !== prevRound) {
      transitionMs = 700; // new round: brief fade to preroll
    } else if (component !== prevComponent) {
      transitionMs = 700; // new component: brief fade
    }
    // same component: instant swap (transitionMs = 0)

    if (transitionMs > 0) {
      startTransition(transitionMs);
    } else {
      snapTo();
    }
  }, [phase, roundNumber, component, stepName, startTransition, snapTo]);

  const total = phaseDuration ?? FALLBACK_DURATIONS[stepName ?? ""] ?? 0;
  const hideTimer = phase === "lobby" || phase === "game_over" || component === "preroll" || transitionState !== "idle" || (component ?? "").endsWith("_results") || timersDisabled;

  return (
    <div className="facility-viewport">
      <div className="facility-vignette" />
      <div style={{ position: "relative", zIndex: 10, width: "100%", height: "100%" }}>
        <FacilityBackground />
        {!hideTimer && <FacilityTimer remaining={remaining} total={total} />}
        <HudPanel />
        <FacilityNarration />
        <TransitionOverlay />
        <FacilityScene />
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
