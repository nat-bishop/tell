"use client";

import { useState } from "react";
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
    myAnswer,
  } = useGameStore();

  const [answer, setAnswer] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const hasSubmitted = submitted || myAnswer !== null;

  const handleSubmit = async () => {
    if (gameId && playerId && !hasSubmitted) {
      setSubmitted(true);
      await submitAnswer(gameId, playerId, answer);
    }
  };

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

      {/* Desk terminal — textarea input or submitted answer */}
      <Panel zone="desk-terminal">
        <div className="flex flex-col items-center justify-center h-full gap-3">
          {!hasSubmitted ? (
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
