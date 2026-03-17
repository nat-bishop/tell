"use client";

import { useState } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { submitQuestion } from "@/api/actions";
import { SystemText } from "./SystemText";
import { GameTextarea } from "./GameTextarea";
import { LabeledCard } from "./LabeledCard";

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
        <p
          className="font-system text-[0.9rem] text-warm tracking-[0.15em] uppercase"
          style={{ textShadow: '0 0 20px var(--glow)' }}
        >
          YOU ARE ON THE HOT SEAT
        </p>
        <p className="font-system text-[0.8rem] text-dim tracking-wide">
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
      <LabeledCard label={`${targetPlayer?.alias || "UNKNOWN"}'s answer`}>
        {targetAnswer ? (
          <p className="font-literary text-[1.1rem] italic leading-[1.6] text-ink">
            {targetAnswer}
          </p>
        ) : (
          <p className="font-system text-[0.85rem] text-dim tracking-wide">
            NO ANSWER SUBMITTED
          </p>
        )}
      </LabeledCard>

      {!spectator && (
        <>
          <hr className="divider" />

          {!hasSubmitted ? (
            <div className="w-full">
              <GameTextarea
                value={question}
                onChange={setQuestion}
                onSubmit={handleSubmit}
                maxLength={200}
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
              <p className="font-literary text-[1.05rem] italic leading-[1.55] text-ink border-l-2 pl-4" style={{ borderColor: 'var(--cold)' }}>
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
