"use client";

import { useState } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { submitResponse } from "@/api/actions";
import { SystemText } from "./SystemText";
import { GameTextarea } from "./GameTextarea";
import { LabeledCard } from "./LabeledCard";

export function RespondPhase({ spectator = false }: { spectator?: boolean }) {
  const {
    gameId,
    playerId,
    players,
    questions,
    roundType,
    nominatedId,
    synthesis,
    responseCount,
    responseTotal,
    myResponseSubmitted,
  } = useGameStore();
  const [response, setResponse] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const hasSubmitted = submitted || myResponseSubmitted;
  const isNominee = playerId === nominatedId;

  // Find the question targeting me
  const myQuestion = questions.find((q) => q.target_id === playerId);
  const questionText =
    roundType === "interrogation" ? synthesis : myQuestion?.question;

  // In interrogation, only nominee responds
  const canRespond =
    roundType === "interrogation" ? isNominee : !!myQuestion;

  const handleSubmit = async () => {
    if (!gameId || !playerId || !response.trim() || hasSubmitted) return;
    setSubmitted(true);
    useGameStore.setState({ myResponseSubmitted: true });
    await submitResponse(gameId, playerId, response.trim());
  };

  if (spectator) {
    return (
      <div className="flex flex-col items-center gap-6 pt-8">
        <SystemText>respond phase</SystemText>
        {roundType === "interrogation" && synthesis && (
          <div className="w-full max-w-md">
            <LabeledCard label="synthesis">
              <p className="font-literary text-[1.05rem] italic leading-[1.6] text-ink">
                {synthesis}
              </p>
            </LabeledCard>
          </div>
        )}
        <SystemText>
          {responseCount} of {responseTotal} responded
        </SystemText>
      </div>
    );
  }

  // No question received (questioner timed out)
  if (!canRespond) {
    return (
      <div className="flex flex-col items-center gap-6 pt-8">
        <SystemText>no question received</SystemText>
        <p className="font-system text-[0.85rem] text-dim tracking-wide">
          awaiting others.
        </p>
        <SystemText>
          {responseCount} of {responseTotal} responded
        </SystemText>
      </div>
    );
  }

  // Interrogation: non-nominee watches
  if (roundType === "interrogation" && !isNominee) {
    const nominee = players.find((p) => p.id === nominatedId);
    return (
      <div className="flex flex-col items-center gap-6 pt-8">
        {synthesis ? (
          <div className="w-full max-w-md">
            <LabeledCard label="synthesis">
              <p className="font-literary text-[1.05rem] italic leading-[1.6] text-ink">
                {synthesis}
              </p>
            </LabeledCard>
          </div>
        ) : (
          <div className="synthesizing-dots font-system text-[0.75rem] text-cold tracking-wide">
            synthesizing
          </div>
        )}
        <p className="font-system text-[0.8rem] text-dim tracking-wide">
          awaiting <span className="text-ink uppercase">{nominee?.alias || "nominee"}</span>&apos;s response...
        </p>
        <SystemText>
          {responseCount} of {responseTotal} responded
        </SystemText>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 pt-4">
      {/* Show the question */}
      <LabeledCard label={roundType === "interrogation" ? "the group asks" : "anonymous question"}>
        <p className="font-literary text-[1.1rem] italic leading-[1.6] text-ink">
          {questionText}
        </p>
      </LabeledCard>

      {!hasSubmitted ? (
        <div className="w-full">
          <GameTextarea
            value={response}
            onChange={setResponse}
            onSubmit={handleSubmit}
            maxLength={400}
            placeholder="your response..."
          />
          <div className="mt-3 flex items-center justify-between">
            <SystemText>
              {responseCount} of {responseTotal} responded
            </SystemText>
            <button
              onClick={handleSubmit}
              disabled={!response.trim()}
              className="btn-action"
            >
              respond &rarr;
            </button>
          </div>
        </div>
      ) : (
        <div className="animate-fade-in">
          <p className="font-literary text-[1.05rem] leading-[1.55] text-ink border-l-2 pl-4" style={{ borderColor: 'var(--cold)' }}>
            {response}
          </p>
          <div className="mt-3 flex items-center justify-between">
            <SystemText>response submitted</SystemText>
            <SystemText>
              {responseCount} of {responseTotal} responded
            </SystemText>
          </div>
        </div>
      )}
    </div>
  );
}
