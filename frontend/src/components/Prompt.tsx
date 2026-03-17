"use client";

import { useState } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { submitAnswer } from "@/api/actions";
import { SystemText } from "./SystemText";

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
      <div className="flex items-center gap-3">
        <SystemText>round {roundNumber}</SystemText>
        {roundType && (
          <SystemText>{roundType}</SystemText>
        )}
      </div>

      <p className="max-w-md text-center font-literary text-[1.3rem] italic leading-[1.6] text-ink">
        {promptText}
      </p>

      {roundType === "task" && promptCategory && (
        <SystemText>{robotJustification[promptCategory] || "task loaded."}</SystemText>
      )}

      {readOnly ? (
        <SystemText>
          {answerCount} of {totalCount} answered
        </SystemText>
      ) : !hasSubmitted ? (
        <div className="w-full max-w-md">
          <textarea
            value={answer}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            onChange={(e) => {
              setAnswer(e.target.value);
              e.target.style.height = "auto";
              e.target.style.height = e.target.scrollHeight + "px";
            }}
            maxLength={280}
            rows={3}
            className="w-full resize-none border-b bg-transparent px-0 py-2 min-h-[44px] font-literary text-[1.1rem] leading-[1.6] text-ink outline-none border-rule"
            placeholder="your answer..."
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
          <div className="border border-rule p-5">
            <p className="font-literary text-[1.05rem] leading-[1.55] text-ink">
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
