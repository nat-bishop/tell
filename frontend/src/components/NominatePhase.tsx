"use client";

import { useState } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { nominate } from "@/api/actions";
import { SystemText } from "./SystemText";

export function NominatePhase({ spectator = false }: { spectator?: boolean }) {
  const {
    gameId,
    playerId,
    players,
    answers,
    nominationCount,
    nominationTotal,
    nominatedId,
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
      <div className="flex flex-col gap-6 pt-4">
        <SystemText>nomination in progress</SystemText>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {alivePlayers.map((p) => {
            const answer = answers[p.id];
            return (
              <div key={p.id} className="border border-rule p-4">
                <div className="font-literary-sc text-[0.85rem] tracking-[0.08em] text-ink">
                  {p.alias}
                </div>
                {answer && (
                  <div className="mt-1 font-literary text-[1rem] leading-[1.5] text-ink">
                    {answer}
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <SystemText>
          {nominationCount} of {nominationTotal} nominated
        </SystemText>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 pt-4">
      <p className="text-center font-literary text-[1.1rem] text-ink">
        who should be interrogated?
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {alivePlayers.map((p) => {
          const answer = answers[p.id];
          const isSelected = selected === p.id;
          return (
            <button
              key={p.id}
              onClick={() => !submitted && setSelected(p.id)}
              disabled={submitted}
              className={`border p-4 text-left transition-colors duration-150 cursor-pointer ${
                !isSelected ? "border-rule" : ""
              }`}
              style={isSelected ? { borderColor: "var(--warm)" } : undefined}
            >
              <div
                className={`font-literary-sc text-[0.85rem] tracking-[0.08em] ${
                  isSelected ? "text-warm" : "text-ink"
                }`}
              >
                {p.alias}
              </div>
              {answer && (
                <div className="mt-1 font-literary text-[1rem] leading-[1.5] text-ink">
                  {answer}
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
