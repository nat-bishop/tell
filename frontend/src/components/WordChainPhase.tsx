"use client";

import { useState } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { submitChainWord } from "@/api/actions";
import { SystemText } from "./SystemText";

export function WordChainPhase({
  spectator = false,
}: {
  spectator?: boolean;
}) {
  const {
    gameId,
    playerId,
    currentSeedWord,
    currentSubRound,
    chainSoFar,
    chainResponseCount,
    chainTotalCount,
  } = useGameStore();

  const [word, setWord] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [lastSubmittedRound, setLastSubmittedRound] = useState(-1);

  // Reset submitted state when sub-round changes
  const isSubmitted = submitted && lastSubmittedRound === currentSubRound;

  const handleSubmit = async () => {
    if (!gameId || !playerId || !word.trim() || isSubmitted) return;
    setSubmitted(true);
    setLastSubmittedRound(currentSubRound);
    await submitChainWord(gameId, playerId, word.trim(), currentSubRound);
    setWord("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSubmit();
  };

  return (
    <div className="flex flex-col items-center gap-8 pt-8">
      <SystemText>word chain</SystemText>

      {/* Growing chain thread */}
      {chainSoFar.length > 0 && (
        <p className="max-w-md text-center font-system text-[0.85rem] text-dim leading-[1.8] tracking-wide">
          {chainSoFar.join(" \u2192 ")}
        </p>
      )}

      {/* Current seed word */}
      <p
        className="font-system text-[2rem] text-ink tracking-[0.1em] uppercase"
        style={{ textShadow: '0 0 20px var(--cold-glow)' }}
      >
        {currentSeedWord || "..."}
      </p>

      {spectator ? (
        <SystemText>
          {chainResponseCount} of {chainTotalCount} submitted
        </SystemText>
      ) : !isSubmitted ? (
        <div className="w-full max-w-xs">
          <input
            value={word}
            onChange={(e) => setWord(e.target.value.replace(/\s/g, ""))}
            onKeyDown={handleKeyDown}
            maxLength={30}
            className="w-full border-b bg-transparent py-2 min-h-[44px] text-center font-literary text-[1.1rem] text-ink outline-none border-rule"
            placeholder="one word..."
            autoFocus
          />
          <div className="mt-4 flex items-center justify-between">
            <SystemText>
              round {currentSubRound + 1} / 8
            </SystemText>
            <button
              onClick={handleSubmit}
              disabled={!word.trim()}
              className="btn-action"
            >
              submit &rarr;
            </button>
          </div>
        </div>
      ) : (
        <div className="w-full max-w-xs text-center">
          <SystemText>word submitted</SystemText>
          <div className="mt-1">
            <SystemText>
              {chainResponseCount} of {chainTotalCount} submitted
            </SystemText>
          </div>
        </div>
      )}
    </div>
  );
}
