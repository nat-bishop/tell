"use client";

import { useEffect, useState } from "react";
import { useGameStore } from "@/hooks/useGameStore";

export function FacilityNarration() {
  const narrationText = useGameStore((s) => s.narrationText);
  const narrationTrigger = useGameStore((s) => s.narrationTrigger);

  const [visible, setVisible] = useState(false);
  const [displayText, setDisplayText] = useState<string | null>(null);
  const [fading, setFading] = useState(false);

  useEffect(() => {
    if (!narrationText) return;

    setDisplayText(narrationText);
    setVisible(true);
    setFading(false);

    if (narrationTrigger === "game_over") return;

    const fadeTimer = setTimeout(() => setFading(true), 6000);
    const hideTimer = setTimeout(() => {
      setVisible(false);
      setDisplayText(null);
    }, 6500);

    return () => {
      clearTimeout(fadeTimer);
      clearTimeout(hideTimer);
    };
  }, [narrationText, narrationTrigger]);

  if (!visible || !displayText) return null;

  return (
    <div
      className={`pointer-events-none fixed bottom-4 left-0 right-0 z-40 flex justify-center px-6 ${
        fading ? "animate-phase-exit" : "animate-fade-in"
      }`}
    >
      <p className="max-w-lg text-center font-literary text-[0.95rem] italic leading-[1.7] text-dim">
        {displayText}
      </p>
    </div>
  );
}
