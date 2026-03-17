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

  // Determine target
  let targetId: string | null = null;
  let isHotSeated = false;
  if (roundType === "interrogation") {
    targetId = nominatedId;
    isHotSeated = playerId === nominatedId;
  } else {
    targetId = playerId ? assignments[playerId] || null : null;
  }

  const targetPlayer = players.find((p) => p.id === targetId);
  const targetAnswer = targetId ? answers[targetId] : null;

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
      {/* Target's answer */}
      <div>
        <SystemText>
          {targetPlayer?.alias || "unknown"}&apos;s answer
        </SystemText>
        {targetAnswer ? (
          <p className="mt-2 font-literary text-[1.1rem] italic leading-[1.6] text-ink">
            {targetAnswer}
          </p>
        ) : (
          <p className="mt-2 font-literary text-[1rem] text-dim">
            no answer submitted
          </p>
        )}
      </div>

      {!spectator && (
        <>
          <hr className="divider" />

          {!hasSubmitted ? (
            <div className="w-full">
              <textarea
                value={question}
                onChange={(e) => {
                  setQuestion(e.target.value);
                  e.target.style.height = "auto";
                  e.target.style.height = e.target.scrollHeight + "px";
                }}
                maxLength={200}
                rows={1}
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
