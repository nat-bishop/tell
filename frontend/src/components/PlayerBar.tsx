"use client";

import { useGameStore } from "@/hooks/useGameStore";

export function PlayerBar() {
  const { players, phase, myVotes, roundNumber } = useGameStore();

  if (phase === "lobby" || phase === "game_over" || phase === "elimination") return null;

  return (
    <div
      className="fixed top-[2px] left-0 right-0 z-40 flex items-center justify-center gap-4 py-2 px-4"
      style={{
        background: 'linear-gradient(180deg, var(--page) 0%, var(--page) 70%, transparent 100%)',
      }}
    >
      {/* Round indicator */}
      <span className="font-system text-[0.6rem] text-cold tracking-widest uppercase">
        r{roundNumber}
      </span>

      {players.map((p) => (
        <div key={p.id} className="flex items-center gap-1.5">
          <span
            className={`inline-block w-1.5 h-1.5 rounded-full transition-all duration-300 ${
              p.is_alive ? "bg-cold" : "bg-rule"
            }`}
          />
          <span
            className={`font-system text-[0.65rem] tracking-[0.1em] uppercase transition-all duration-300 ${
              p.is_alive ? "text-ink" : "text-dim line-through"
            }`}
          >
            {p.alias}
          </span>
          {phase === "review" && myVotes.includes(p.id) && (
            <span
              className="inline-block w-1.5 h-1.5 rounded-full bg-warm"
              style={{ boxShadow: '0 0 6px var(--warm)' }}
            />
          )}
        </div>
      ))}
    </div>
  );
}
