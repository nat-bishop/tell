"use client";

import { useState, useEffect } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { submitAnswer } from "@/api/actions";
import { SystemText } from "./SystemText";
import { GameTextarea } from "./GameTextarea";

const robotJustification: Record<string, string> = {
  haiku: "5-7-5 syllable structure. trivially optimizable.",
  concise: "compression is a core capability.",
  humor: "humor is pattern recognition plus subverted expectations.",
  corporate: "professional communication. template-optimized.",
  casual: "informal register. social protocol adaptation.",
  style: "style transfer. straightforward transformation matrix.",
  emotional_task: "emotional response templates loaded.",
};

export function Prompt({ readOnly = false }: { readOnly?: boolean }) {
  const {
    gameId,
    playerId,
    roundNumber,
    promptText,
    promptCategory,
    answerCount,
    totalCount,
    myAnswer,
    roundType,
    writingBeginsAt,
    myMatchupPrompt,
    byePlayerId,
  } = useGameStore();
  const [answer, setAnswer] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [writingOpen, setWritingOpen] = useState(false);

  // Track reading period → writing period transition
  useEffect(() => {
    if (!writingBeginsAt) {
      setWritingOpen(true);
      return;
    }

    const now = Date.now();
    const writingAt = new Date(writingBeginsAt).getTime();
    const remaining = writingAt - now;

    if (remaining <= 0) {
      setWritingOpen(true);
      return;
    }

    setWritingOpen(false);
    const timer = setTimeout(() => setWritingOpen(true), remaining);
    return () => clearTimeout(timer);
  }, [writingBeginsAt]);

  const hasSubmitted = submitted || myAnswer !== null;

  const handleSubmit = async () => {
    if (gameId && playerId && !hasSubmitted) {
      setSubmitted(true);
      await submitAnswer(gameId, playerId, answer);
    }
  };

  const isReading = !writingOpen;
  const isBye = roundType === "task" && byePlayerId === playerId;
  const displayPrompt = myMatchupPrompt ?? promptText;
  const justification = roundType === "task" && promptCategory
    ? robotJustification[promptCategory] || "task loaded."
    : null;

  return (
    <div className="flex flex-col items-center gap-8 pt-8">
      <div className="flex items-center gap-3">
        <SystemText>round {roundNumber}</SystemText>
        {roundType && (
          <SystemText>{roundType}</SystemText>
        )}
      </div>

      {isBye ? (
        <div className="flex flex-col items-center gap-4">
          <p className="max-w-md text-center font-literary text-[1.2rem] italic leading-[1.6] text-dim">
            you have a bye this round
          </p>
          <SystemText>you&apos;ll vote on matchups next</SystemText>
        </div>
      ) : (
        <p className="max-w-md text-center font-literary text-[1.3rem] italic leading-[1.6] text-ink">
          {displayPrompt}
        </p>
      )}

      {justification && (
        <div
          className="animate-fade-in"
          style={{ animationDelay: isReading ? "3s" : "0s" }}
        >
          <SystemText>{justification}</SystemText>
        </div>
      )}

      {readOnly ? (
        <SystemText>
          {answerCount} of {totalCount} answered
        </SystemText>
      ) : isReading ? (
        /* Reading period — prompt visible, no input */
        null
      ) : !hasSubmitted ? (
        <div className="w-full max-w-md animate-fade-in">
          <GameTextarea
            value={answer}
            onChange={setAnswer}
            onSubmit={handleSubmit}
            maxLength={280}
            placeholder="your answer..."
            autoFocus
          />
          <div className="mt-4 flex items-center justify-between">
            <SystemText>
              {answerCount} of {totalCount} answered
            </SystemText>
            <button
              onClick={handleSubmit}
              className="btn-action"
            >
              submit &rarr;
            </button>
          </div>
        </div>
      ) : (
        <div className="w-full max-w-md animate-fade-in">
          <div className="submitted-panel">
            <p className="font-literary text-[1.1rem] leading-[1.6] text-ink">
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
  );
}
