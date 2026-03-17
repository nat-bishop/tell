"use client";

import { useGameStore } from "@/hooks/useGameStore";

export function PlayerBar() {
  const { players, phase, myVotes, roundNumber } = useGameStore();

  if (phase === "lobby" || phase === "game_over" || phase === "elimination") return null;

  return (
    <div className="fixed top-[2px] left-0 right-0 z-40 flex items-center justify-center gap-4 py-2 px-4 bg-page">
      {/* Round indicator */}
      <span className="font-system text-[0.6rem] text-dim tracking-wide">
        r{roundNumber}
      </span>

      {players.map((p) => (
        <div key={p.id} className="flex items-center gap-1.5">
          <span
            className={`inline-block w-1.5 h-1.5 rounded-full transition-all duration-300 ${
              p.is_alive ? "bg-ink" : "bg-rule"
            }`}
          />
          <span
            className={`font-literary-sc text-[0.7rem] tracking-[0.08em] transition-all duration-300 ${
              p.is_alive ? "text-ink" : "text-dim line-through"
            }`}
          >
            {p.alias}
          </span>
          {phase === "review" && myVotes.includes(p.id) && (
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-warm" />
          )}
        </div>
      ))}
    </div>
  );
}
