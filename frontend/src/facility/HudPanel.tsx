"use client";

import { useGameStore } from "@/hooks/useGameStore";
import { usePlayerColors } from "./usePlayerColors";

export function HudPanel() {
  const { players, phase, roundNumber, scores } = useGameStore();

  const colorMap = usePlayerColors();

  if (phase === "lobby" || phase === "game_over") return null;

  return (
    <div
      className="fixed top-[6px] left-0 right-0 z-40 flex items-center justify-center gap-4 py-1.5 px-4"
      style={{
        background: "linear-gradient(180deg, rgba(0,0,0,0.3) 0%, transparent 100%)",
      }}
    >
      <span className="font-system text-[0.6rem] text-cold tracking-widest uppercase">
        r{roundNumber}
      </span>

      {players.map((p) => {
        const playerScore = scores[p.id] ?? 0;
        const dotColor = colorMap[p.id] ?? "var(--cold)";
        return (
          <div key={p.id} className="flex items-center gap-1.5">
            <span
              className="inline-block w-1.5 h-1.5 rounded-full"
              style={{
                backgroundColor: dotColor,
                boxShadow: `0 0 4px ${dotColor}40`,
              }}
            />
            <span className="font-system text-[0.6rem] tracking-[0.1em] uppercase text-ink">
              {p.alias}
            </span>
            {playerScore > 0 && (
              <span className="font-system text-[0.55rem] text-warm tracking-wider">
                {playerScore}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
