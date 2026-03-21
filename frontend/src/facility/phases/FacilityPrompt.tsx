"use client";

import { useState, useCallback } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { submitAnswer } from "@/api/actions";
import { Panel } from "@/facility/Panel";
import { SystemText } from "@/components/SystemText";
import { GameTextarea } from "@/components/GameTextarea";

export function FacilityPrompt() {
  const {
    gameId,
    playerId,
    roundNumber,
    promptText,
    answerCount,
    totalCount,
  } = useGameStore();

  const [answer, setAnswer] = useState("");
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [pending, setPending] = useState(false);

  const handleSubmit = useCallback(async () => {
    if (!gameId || !playerId || !answer.trim() || pending) return;
    setPending(true);
    try {
      await submitAnswer(gameId, playerId, answer);
      setHasSubmitted(true);
    } catch {
      // Silently handle
    }
    setPending(false);
  }, [gameId, playerId, answer, pending]);

  return (
    <>
      {/* Wall display — round info + prompt */}
      <Panel zone="wall-display">
        <div className="flex flex-col items-center gap-4 h-full justify-center">
          <SystemText>round {roundNumber}</SystemText>

          <p className="max-w-md text-center font-literary text-[1.2rem] italic leading-[1.6] text-ink">
            {promptText}
          </p>
        </div>
      </Panel>

      {/* Desk terminal — textarea input */}
      <Panel zone="desk-terminal">
        <div className="flex flex-col items-center justify-center h-full gap-3">
          <div className="w-full max-w-md animate-fade-in">
            <GameTextarea
              value={answer}
              onChange={setAnswer}
              onSubmit={handleSubmit}
              maxLength={280}
              placeholder="your answer..."
              autoFocus
            />
            <div className="mt-3 flex items-center justify-between">
              <SystemText>
                {hasSubmitted ? "answer submitted" : `${answerCount} of ${totalCount} answered`}
              </SystemText>
              <button onClick={handleSubmit} className="btn-action" disabled={pending || !answer.trim()}>
                {hasSubmitted ? "update" : "submit"} &rarr;
              </button>
            </div>
          </div>
        </div>
      </Panel>
    </>
  );
}
