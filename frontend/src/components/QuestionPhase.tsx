"use client";

import { useState } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { submitQuestion } from "@/api/actions";
import { SystemText } from "./SystemText";

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
        <p className="font-literary text-[1.1rem] text-ink text-center">
          you are on the hot seat
        </p>
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
      {/* Player answer cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {alivePlayers.map((p) => {
          const answer = answers[p.id];
          const isTarget = p.id === targetId;
          return (
            <div
              key={p.id}
              className={`border p-4 ${isTarget ? "" : "border-rule"}`}
              style={isTarget ? { borderColor: "var(--warm)" } : undefined}
            >
              <div
                className={`font-literary-sc text-[0.85rem] tracking-[0.08em] ${
                  isTarget ? "text-warm" : "text-ink"
                }`}
              >
                {p.alias}
              </div>
              {isTarget && !spectator && (
                <div className="mt-0.5 font-system text-[0.65rem] text-warm">
                  your target
                </div>
              )}
              {answer && (
                <div className="mt-1 font-literary text-[1rem] leading-[1.5] text-ink">
                  {answer}
                </div>
              )}
            </div>
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
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit();
                  }
                }}
                onChange={(e) => {
                  setQuestion(e.target.value);
                  e.target.style.height = "auto";
                  e.target.style.height = e.target.scrollHeight + "px";
                }}
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
                  className="btn-action"
                >
                  ask &rarr;
                </button>
              </div>
            </div>
          ) : (
            <div className="animate-fade-in">
              <p className="font-literary text-[1.05rem] italic leading-[1.55] text-ink border-l-2 border-rule pl-4">
                {question}
              </p>
              <div className="mt-3 flex items-center justify-between">
                <SystemText>question submitted</SystemText>
                <SystemText>
                  {questionCount} of {questionTotal} submitted
                </SystemText>
              </div>
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
