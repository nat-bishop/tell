"use client";

import { useEffect, useState } from "react";
import { useGameStore } from "@/hooks/useGameStore";

/**
 * Narration — displays narrator lines as they arrive via SSE.
 * Fades in, holds, then fades out. Positioned as a floating overlay
 * or inline depending on the trigger context.
 */
export function Narration({ position = "bottom" }: { position?: "top" | "bottom" | "center" }) {
  const narrationText = useGameStore((s) => s.narrationText);
  const narrationTrigger = useGameStore((s) => s.narrationTrigger);

  const [visible, setVisible] = useState(false);
  const [displayText, setDisplayText] = useState<string | null>(null);
  const [fading, setFading] = useState(false);

  useEffect(() => {
    if (!narrationText) {
      return;
    }

    setDisplayText(narrationText);
    setVisible(true);
    setFading(false);

    // Auto-dismiss after hold period (unless game_over, which persists)
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

  const positionClass =
    position === "top"
      ? "top-4"
      : position === "center"
        ? "top-1/2 -translate-y-1/2"
        : "bottom-8";

  return (
    <div
      className={`pointer-events-none fixed left-0 right-0 z-40 flex justify-center px-6 ${positionClass} ${
        fading ? "animate-phase-exit" : "animate-fade-in"
      }`}
    >
      <p className="max-w-lg text-center font-literary text-[0.95rem] italic leading-[1.7] text-dim">
        {displayText}
      </p>
    </div>
  );
}

/**
 * Inline narration for game_over — not floating, part of the layout.
 */
export function NarrationInline() {
  const narrationText = useGameStore((s) => s.narrationText);
  const narrationTrigger = useGameStore((s) => s.narrationTrigger);

  if (!narrationText || narrationTrigger !== "game_over") return null;

  return (
    <p className="animate-fade-in max-w-md text-center font-literary text-[1rem] italic leading-[1.7] text-dim">
      {narrationText}
    </p>
  );
}
