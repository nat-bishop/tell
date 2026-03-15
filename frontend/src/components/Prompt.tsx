"use client";

import { useState } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { submitAnswer } from "@/api/actions";
import { SystemText } from "./SystemText";

export function Prompt() {
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
    <div className="flex flex-col items-center gap-8 pt-8">
      <SystemText>round {roundNumber}</SystemText>

      <p
        className="max-w-md text-center font-[family-name:var(--font-literary)] text-[1.3rem] italic leading-[1.6]"
        style={{ color: "var(--ink)" }}
      >
        {promptText}
      </p>

      {!hasSubmitted ? (
        <div className="w-full max-w-md">
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            maxLength={280}
            rows={3}
            className="w-full resize-none border-b bg-transparent px-0 py-2 font-[family-name:var(--font-literary)] text-[1.1rem] leading-[1.6] outline-none"
            style={{
              color: "var(--ink)",
              borderColor: "var(--rule)",
            }}
            placeholder="your answer..."
          />
          <div className="mt-4 flex items-center justify-between">
            <SystemText>
              {answerCount} of {totalCount} answered
            </SystemText>
            <button
              onClick={handleSubmit}
              className="font-[family-name:var(--font-literary)] text-[1rem] transition-opacity hover:opacity-70"
              style={{ color: "var(--ink)" }}
            >
              submit &rarr;
            </button>
          </div>
        </div>
      ) : (
        <div className="w-full max-w-md">
          <SystemText>answer submitted</SystemText>
          <SystemText>
            {answerCount} of {totalCount} answered
          </SystemText>
        </div>
      )}
    </div>
  );
}
