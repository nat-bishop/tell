"use client";

import { useState, useEffect } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { submitAnswer, getSignalPhrase } from "@/api/actions";
import { Panel } from "@/facility/Panel";
import { SystemText } from "@/components/SystemText";
import { GameTextarea } from "@/components/GameTextarea";

export function FacilitySignalPrompt() {
  const {
    gameId,
    playerId,
    roundNumber,
    promptText,
    answerCount,
    totalCount,
    myAnswer,
    signalPhrase,
  } = useGameStore();

  const [phrase, setPhrase] = useState<string | null>(signalPhrase);
  const [answer, setAnswer] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const hasSubmitted = submitted || myAnswer !== null;

  // Fetch signal phrase on mount (or use reconnection data)
  useEffect(() => {
    if (phrase) return;
    if (!gameId || !playerId) return;

    getSignalPhrase(gameId, playerId)
      .then((data) => setPhrase(data.phrase))
      .catch(() => {});
  }, [gameId, playerId, phrase]);

  const handleSubmit = async () => {
    if (gameId && playerId && !hasSubmitted) {
      try {
        await submitAnswer(gameId, playerId, answer);
        setSubmitted(true);
      } catch {
        // allow retry
      }
    }
  };

  return (
    <>
      {/* Wall display — constraint */}
      <Panel zone="wall-display">
        <div className="flex flex-col items-center gap-4 h-full justify-center">
          <SystemText>round {roundNumber} / signal</SystemText>
          <p className="font-system text-[0.65rem] text-cold tracking-[0.2em] uppercase">
            constraint
          </p>
          <p className="max-w-md text-center font-literary text-[1.2rem] italic leading-[1.6] text-ink">
            {promptText}
          </p>
        </div>
      </Panel>

      {/* Desk terminal — phrase + transformation input */}
      <Panel zone="desk-terminal">
        <div className="flex flex-col items-center justify-center h-full gap-3">
          {phrase && (
            <div className="w-full max-w-md">
              <p className="font-system text-[0.6rem] text-dim tracking-[0.15em] uppercase mb-1">
                your secret phrase
              </p>
              <p className="font-literary text-[1.05rem] text-ink leading-[1.6] mb-4 p-3 border border-rule rounded-sm bg-surface">
                {phrase}
              </p>
            </div>
          )}

          {!hasSubmitted ? (
            <div className="w-full max-w-md animate-fade-in">
              <GameTextarea
                value={answer}
                onChange={setAnswer}
                onSubmit={handleSubmit}
                maxLength={280}
                placeholder="transform the phrase..."
                autoFocus
              />
              <div className="mt-3 flex items-center justify-between">
                <SystemText>
                  {answerCount} of {totalCount} answered
                </SystemText>
                <button onClick={handleSubmit} className="btn-action">
                  submit &rarr;
                </button>
              </div>
            </div>
          ) : (
            <div className="w-full max-w-md animate-fade-in">
              <div className="submitted-panel">
                <p className="font-literary text-[1.05rem] leading-[1.6] text-ink">
                  {answer || myAnswer}
                </p>
              </div>
              <div className="mt-3 flex items-center justify-between">
                <SystemText>submitted</SystemText>
                <SystemText>
                  {answerCount} of {totalCount} answered
                </SystemText>
              </div>
            </div>
          )}
        </div>
      </Panel>
    </>
  );
}
