"use client";

import { useGameStore, type RevealedPlayer } from "@/hooks/useGameStore";
import { createGame } from "@/api/actions";
import { useRouter } from "next/navigation";

export function GameOver() {
  const { winner, revealedPlayers } = useGameStore();
  const router = useRouter();

  const handlePlayAgain = async () => {
    const res = await createGame();
    router.push(`/game/${res.game_id}`);
  };

  // Sort: eliminated first (by round), then survivors
  const sorted = [...(revealedPlayers || [])].sort(
    (a, b) => {
      if (!a.is_alive && b.is_alive) return -1;
      if (a.is_alive && !b.is_alive) return 1;
      if (!a.is_alive && !b.is_alive)
        return (a.eliminated_round || 0) - (b.eliminated_round || 0);
      return 0;
    },
  );

  const totalPlayers = sorted.length;

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-10">
      <p className="animate-elimination-reveal font-literary text-[1.5rem] text-ink">
        {winner === "ai" ? "the machines win." : "humanity survives."}
      </p>

      <div className="flex flex-col gap-3">
        {sorted.map((p, i) => (
          <div
            key={p.id}
            className="flex items-center gap-4 min-h-[44px] animate-fade-in"
            style={{ animationDelay: `${(i * 400) + 1000}ms` }}
          >
            <span
              className={`w-24 font-literary-sc text-[0.9rem] tracking-[0.08em] ${p.is_alive ? 'text-ink' : 'text-dim line-through'}`}
            >
              {p.alias}
            </span>
            <span
              className={`font-literary text-[1rem] ${p.role === 'human' ? 'text-warm' : 'text-dim'}`}
            >
              {p.role}
            </span>
            {!p.is_alive && (
              <span className="font-system text-[0.7rem] text-dim">
                round {p.eliminated_round}
              </span>
            )}
          </div>
        ))}
      </div>

      <button
        onClick={handlePlayAgain}
        className="btn-action animate-fade-in"
        style={{ animationDelay: `${(totalPlayers * 400) + 2000}ms` }}
      >
        play again &rarr;
      </button>
    </div>
  );
}
