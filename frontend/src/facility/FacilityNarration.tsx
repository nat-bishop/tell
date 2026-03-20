"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useGameStore } from "@/hooks/useGameStore";

type Phase = "idle" | "typing" | "hold" | "fadeout";

export function FacilityNarration() {
  const narrationText = useGameStore((s) => s.narrationText);
  const narrationTrigger = useGameStore((s) => s.narrationTrigger);

  const [phase, setPhase] = useState<Phase>("idle");
  const [text, setText] = useState<string | null>(null);
  const [revealedCount, setRevealedCount] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const holdTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fadeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Clear all timers
  const clearTimers = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (holdTimerRef.current) clearTimeout(holdTimerRef.current);
    if (fadeTimerRef.current) clearTimeout(fadeTimerRef.current);
    intervalRef.current = null;
    holdTimerRef.current = null;
    fadeTimerRef.current = null;
  }, []);

  // New narration text arrived — start typing
  useEffect(() => {
    if (!narrationText) return;

    clearTimers();
    setText(narrationText);
    setRevealedCount(0);
    setPhase("typing");

    // Adaptive speed: ~33ms/char, capped at 2.5s total
    const charDelay = Math.min(33, 2500 / narrationText.length);
    let count = 0;

    intervalRef.current = setInterval(() => {
      count++;
      setRevealedCount(count);
      if (count >= narrationText.length) {
        if (intervalRef.current) clearInterval(intervalRef.current);
        intervalRef.current = null;
        setPhase("hold");
      }
    }, charDelay);

    return clearTimers;
  }, [narrationText, clearTimers]);

  // Hold → fadeout → idle (skip for game_over)
  useEffect(() => {
    if (phase !== "hold") return;
    if (narrationTrigger === "game_over") return;

    holdTimerRef.current = setTimeout(() => setPhase("fadeout"), 8000);
    return () => {
      if (holdTimerRef.current) clearTimeout(holdTimerRef.current);
    };
  }, [phase, narrationTrigger]);

  useEffect(() => {
    if (phase !== "fadeout") return;

    fadeTimerRef.current = setTimeout(() => {
      setPhase("idle");
      setText(null);
    }, 500);
    return () => {
      if (fadeTimerRef.current) clearTimeout(fadeTimerRef.current);
    };
  }, [phase]);

  if (phase === "idle" || !text) return null;

  const isTyping = phase === "typing";
  const isFading = phase === "fadeout";

  return (
    <div
      className={`pointer-events-none fixed bottom-0 left-0 right-0 z-40 ${
        isFading ? "animate-phase-exit" : "animate-fade-in"
      }`}
      style={{
        background: "rgba(15, 17, 20, 0.6)",
        backdropFilter: "blur(8px)",
        borderTop: "1px solid var(--rule)",
        boxShadow: "0 -1px 20px rgba(91, 143, 185, 0.08)",
      }}
    >
      <p
        className="mx-auto max-w-2xl px-[10%] py-3 text-center font-literary text-base leading-[1.7]"
        style={{ color: "var(--cold)" }}
      >
        <span>{text.slice(0, revealedCount)}</span>
        {isTyping && (
          <span
            className="inline-block w-[2px] align-baseline"
            style={{
              height: "1em",
              background: "var(--cold)",
              animation: "cursor-blink 600ms step-end infinite",
              marginLeft: "1px",
            }}
          />
        )}
        <span className="invisible">{text.slice(revealedCount)}</span>
      </p>
    </div>
  );
}
