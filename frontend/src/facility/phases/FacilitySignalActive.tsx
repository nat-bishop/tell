"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { submitSignalGuess } from "@/api/actions";
import { Panel } from "@/facility/Panel";
import { SystemText } from "@/components/SystemText";
import { GameTextarea } from "@/components/GameTextarea";

export function FacilitySignalActive() {
  const gameId = useGameStore((s) => s.gameId);
  const playerId = useGameStore((s) => s.playerId);
  const subRoundPayload = useGameStore((s) => s.subRoundPayload);
  const subRoundIndex = useGameStore((s) => s.subRoundIndex);
  const isTransmitter = useGameStore((s) => s.isTransmitter);

  const isSignal = subRoundPayload?.round_type === "signal";
  const featuredAlias = isSignal ? subRoundPayload.featured_alias : null;
  const transformation = isSignal ? subRoundPayload.transformation : null;
  const constraint = isSignal ? subRoundPayload.constraint : null;
  const totalTransmitters = isSignal ? (subRoundPayload.total_transmitters ?? 3) : 3;

  const [guess, setGuess] = useState("");
  const [lastSubmittedIndex, setLastSubmittedIndex] = useState(-1);
  const prevSubRoundRef = useRef(subRoundIndex);
  const guessRef = useRef(guess);
  useEffect(() => { guessRef.current = guess; }, [guess]);

  // Auto-submit pending guess when sub-round changes
  useEffect(() => {
    const prevSubRound = prevSubRoundRef.current;
    if (prevSubRound !== subRoundIndex && guessRef.current.trim() && gameId && playerId) {
      submitSignalGuess(gameId, playerId, guessRef.current.trim(), prevSubRound).catch(() => {});
    }
    prevSubRoundRef.current = subRoundIndex;
    setGuess("");
    setLastSubmittedIndex(-1);
  }, [subRoundIndex, gameId, playerId]);

  const handleSubmit = useCallback(async () => {
    if (!gameId || !playerId || !guess.trim() || isTransmitter) return;
    try {
      await submitSignalGuess(gameId, playerId, guess.trim(), subRoundIndex);
      setLastSubmittedIndex(subRoundIndex);
    } catch {
      // Silently handle — phase changed or already submitted
    }
  }, [gameId, playerId, guess, subRoundIndex, isTransmitter]);

  const hasSubmitted = lastSubmittedIndex === subRoundIndex;

  if (!isSignal) {
    return (
      <Panel zone="main-screen">
        <div className="flex items-center justify-center h-full">
          <SystemText>waiting for signal...</SystemText>
        </div>
      </Panel>
    );
  }

  return (
    <>
      {/* Main screen — featured transformation */}
      <Panel zone="main-screen">
        <div className="flex flex-col items-center justify-center h-full gap-4">
          <p className="font-system text-[0.65rem] text-cold tracking-[0.2em] uppercase">
            {constraint} &mdash; {featuredAlias}&apos;s signal
          </p>

          <p className="font-system text-[0.55rem] text-dim tracking-[0.15em] uppercase">
            {subRoundIndex + 1} of {totalTransmitters}
          </p>

          <p className="font-literary text-[1.2rem] text-ink text-center leading-[1.6] max-w-md italic">
            {transformation}
          </p>
        </div>
      </Panel>

      {/* Center area — guess input or transmitter message */}
      <Panel zone="center-area">
        <div className="flex flex-col items-center justify-center h-full gap-3">
          {isTransmitter ? (
            <div className="w-full max-w-sm text-center animate-fade-in">
              <p className="font-system text-[0.75rem] text-dim tracking-wider uppercase">
                waiting for guesses...
              </p>
            </div>
          ) : (
            <div className="w-full max-w-sm animate-fade-in">
              <p className="font-system text-[0.6rem] text-dim tracking-[0.15em] uppercase mb-2 text-center">
                what was the original phrase?
              </p>
              <GameTextarea
                value={guess}
                onChange={setGuess}
                onSubmit={handleSubmit}
                maxLength={200}
                placeholder="your guess..."
                autoFocus
              />
              <div className="mt-3 flex items-center justify-center">
                <button
                  onClick={handleSubmit}
                  className="btn-action"
                  disabled={!guess.trim()}
                >
                  {hasSubmitted ? "update" : "submit"} &rarr;
                </button>
              </div>
              {hasSubmitted && (
                <p className="mt-1 text-center font-system text-[0.6rem] text-dim tracking-wider">
                  guess submitted
                </p>
              )}
            </div>
          )}
        </div>
      </Panel>
    </>
  );
}
