"use client";

import { useState } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { useAnswerEntries } from "@/hooks/useAnswerEntries";
import { nominate } from "@/api/actions";
import { Dialogue } from "./Dialogue";
import { SystemText } from "./SystemText";

export function NominatePhase({ spectator = false }: { spectator?: boolean }) {
  const {
    gameId,
    playerId,
    players,
    nominationCount,
    nominationTotal,
    nominatedId,
  } = useGameStore();
  const answerEntries = useAnswerEntries();
  const [selected, setSelected] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const alivePlayers = players.filter((p) => p.is_alive);

  // Already nominated
  if (nominatedId) {
    const nominee = players.find((p) => p.id === nominatedId);
    return (
      <div className="flex flex-col items-center gap-6 pt-8">
        <SystemText>nominated for the hot seat</SystemText>
        <p className="font-literary-sc text-[1.3rem] tracking-[0.08em] text-warm animate-fade-in">
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
      <div className="flex flex-col items-center gap-6 pt-8">
        <SystemText>nomination in progress</SystemText>
        <div className="w-full space-y-5">
          {answerEntries.map((entry, i) => (
            <Dialogue key={i} alias={entry.alias} text={entry.text} animate={false} />
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
      <SystemText>who should be interrogated?</SystemText>

      {/* Show answers with selectable players */}
      <div className="space-y-4">
        {alivePlayers.map((p) => {
          const entry = answerEntries.find((e) => e.alias === p.alias);
          return (
            <button
              key={p.id}
              onClick={() => !submitted && setSelected(p.id)}
              disabled={submitted}
              className="w-full text-left py-3 pl-3 transition-all"
              style={{
                borderLeft:
                  selected === p.id
                    ? "3px solid var(--warm)"
                    : "3px solid transparent",
              }}
            >
              <div
                className={`font-literary-sc text-[0.9rem] tracking-[0.08em] ${
                  selected === p.id ? "text-warm" : "text-ink"
                }`}
              >
                {p.alias}
              </div>
              {entry && (
                <div className="mt-1 font-literary text-[1rem] leading-[1.5] text-ink">
                  {entry.text}
                </div>
              )}
            </button>
          );
        })}
      </div>

      <div className="flex items-center justify-between">
        <SystemText>
          {nominationCount} of {nominationTotal} nominated
        </SystemText>
        {!submitted && selected && (
          <button
            onClick={handleNominate}
            className="font-literary text-[1rem] min-h-[44px] px-2 text-ink transition-opacity hover:opacity-70"
          >
            nominate &rarr;
          </button>
        )}
        {submitted && <SystemText>nomination cast</SystemText>}
      </div>
    </div>
  );
}
