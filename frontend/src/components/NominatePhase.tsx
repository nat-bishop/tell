"use client";

import { useState } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { nominate } from "@/api/actions";
import { SystemText } from "./SystemText";
import { AnswerCard } from "./AnswerCard";

export function NominatePhase({ spectator = false }: { spectator?: boolean }) {
  const {
    gameId,
    playerId,
    players,
    answers,
    nominationCount,
    nominationTotal,
    nominatedId,
    promptText,
  } = useGameStore();
  const [selected, setSelected] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const alivePlayers = players.filter((p) => p.is_alive);

  // Already nominated
  if (nominatedId) {
    const nominee = players.find((p) => p.id === nominatedId);
    return (
      <div className="flex flex-col items-center gap-6 pt-8">
        <SystemText>nominated for the hot seat</SystemText>
        <p
          className="font-system text-[1.1rem] tracking-[0.15em] uppercase text-warm animate-fade-in"
          style={{ textShadow: '0 0 20px var(--glow)' }}
        >
          {nominee?.alias || "???"}
        </p>
      </div>
    );
  }

  const handleNominate = async () => {
    if (!gameId || !playerId || !selected || submitted) return;
    setSubmitted(true);
    await nominate(gameId, playerId, selected);
  };

  if (spectator) {
    return (
      <div className="flex flex-col gap-6 pt-4">
        <SystemText>nomination in progress</SystemText>

        {promptText && (
          <p className="text-center font-literary text-[1.1rem] italic leading-[1.6] text-dim">
            {promptText}
          </p>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:[grid-auto-rows:1fr]">
          {alivePlayers.map((p) => (
            <AnswerCard
              key={p.id}
              alias={p.alias}
              answer={answers[p.id]}
            />
          ))}
        </div>

        <SystemText>
          {nominationCount} of {nominationTotal} nominated
        </SystemText>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 pt-4">
      <p className="text-center font-system text-[0.9rem] text-ink tracking-[0.15em] uppercase">
        SELECT TARGET
      </p>

      {promptText && (
        <p className="text-center font-literary text-[1.1rem] italic leading-[1.6] text-dim">
          {promptText}
        </p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:[grid-auto-rows:1fr]">
        {alivePlayers.map((p) => (
          <AnswerCard
            key={p.id}
            alias={p.alias}
            answer={answers[p.id]}
            highlighted={selected === p.id}
            as="button"
            onClick={() => !submitted && setSelected(p.id)}
            disabled={submitted}
          />
        ))}
      </div>

      <div className="flex items-center justify-between">
        <SystemText>
          {nominationCount} of {nominationTotal} nominated
        </SystemText>
        {!submitted && selected && (
          <button
            onClick={handleNominate}
            className="btn-action"
          >
            nominate &rarr;
          </button>
        )}
        {submitted && <SystemText>nomination cast</SystemText>}
      </div>
    </div>
  );
}
