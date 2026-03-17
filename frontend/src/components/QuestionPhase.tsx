"use client";

import { useState } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { submitQuestion } from "@/api/actions";
import { SystemText } from "./SystemText";
import { AnswerCard } from "./AnswerCard";

export function QuestionPhase({ spectator = false }: { spectator?: boolean }) {
  const {
    gameId,
    playerId,
    players,
    answers,
    assignments,
    roundType,
    nominatedId,
    questionCount,
    questionTotal,
    myQuestionSubmitted,
    promptText,
  } = useGameStore();
  const [question, setQuestion] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const hasSubmitted = submitted || myQuestionSubmitted;
  const alivePlayers = players.filter((p) => p.is_alive);

  // Determine target
  let targetId: string | null = null;
  let isHotSeated = false;
  if (roundType === "interrogation") {
    targetId = nominatedId;
    isHotSeated = playerId === nominatedId;
  } else {
    targetId = playerId ? assignments[playerId] || null : null;
  }

  const handleSubmit = async () => {
    if (!gameId || !playerId || !question.trim() || hasSubmitted) return;
    setSubmitted(true);
    useGameStore.setState({ myQuestionSubmitted: true });
    await submitQuestion(gameId, playerId, question.trim());
  };

  // Hot-seated player in interrogation just waits
  if (isHotSeated) {
    return (
      <div className="flex flex-col items-center gap-8 pt-8">
        <SystemText>you are on the hot seat</SystemText>
        <p className="font-literary text-[1.1rem] text-dim text-center">
          awaiting questions from the group...
        </p>
        <SystemText>
          {questionCount} of {questionTotal} submitted
        </SystemText>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 pt-4">
      {promptText && (
        <p className="text-center font-literary text-[1.1rem] italic leading-[1.6] text-dim">
          {promptText}
        </p>
      )}

      {/* Player answer cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:[grid-auto-rows:1fr]">
        {alivePlayers.map((p) => {
          const isTarget = p.id === targetId;
          return (
            <AnswerCard
              key={p.id}
              alias={p.alias}
              answer={answers[p.id]}
              highlighted={isTarget}
              label={isTarget && !spectator ? "your target" : undefined}
            />
          );
        })}
      </div>

      {!spectator && (
        <>
          <hr className="divider" />

          {!hasSubmitted ? (
            <div className="w-full">
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                maxLength={200}
                rows={2}
                className="w-full resize-none border-b bg-transparent px-0 py-2 min-h-[44px] font-literary text-[1.05rem] leading-[1.6] text-ink outline-none border-rule"
                placeholder={
                  roundType === "interrogation"
                    ? "your question for the nominee..."
                    : "your anonymous question..."
                }
              />
              <div className="mt-3 flex items-center justify-between">
                <SystemText>
                  {questionCount} of {questionTotal} submitted
                </SystemText>
                <button
                  onClick={handleSubmit}
                  disabled={!question.trim()}
                  className="font-literary text-[1rem] min-h-[44px] px-2 text-ink transition-opacity hover:opacity-70 disabled:opacity-30"
                >
                  ask &rarr;
                </button>
              </div>
            </div>
          ) : (
            <div>
              <SystemText>question submitted</SystemText>
              <SystemText>
                {questionCount} of {questionTotal} submitted
              </SystemText>
            </div>
          )}
        </>
      )}

      {spectator && (
        <SystemText>
          {questionCount} of {questionTotal} submitted
        </SystemText>
      )}
    </div>
  );
}
