"use client";

import { useGameStore } from "@/hooks/useGameStore";
import { createGame } from "@/api/actions";
import { useRouter } from "next/navigation";

interface RevealedPlayer {
  id: string;
  alias: string;
  role: string;
  is_alive: boolean;
  eliminated_round?: number;
}

export function GameOver() {
  const { winner, revealedPlayers } = useGameStore();
  const router = useRouter();

  const handlePlayAgain = async () => {
    const res = await createGame();
    router.push(`/game/${res.game_id}`);
  };

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-10">
      <p className="animate-fade-in font-literary text-[1.5rem] text-ink">
        {winner === "ai" ? "the machines win." : "humanity survives."}
      </p>

      <div className="flex flex-col gap-3">
        {(revealedPlayers as RevealedPlayer[] | null)?.map((p) => (
          <div
            key={p.id}
            className="flex items-center gap-4 min-h-[44px] animate-fade-in"
          >
            <span
              className={`w-24 font-literary-sc text-[0.9rem] tracking-[0.08em] ${p.is_alive ? 'text-ink' : 'text-dim'}`}
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
                (voted off, round {p.eliminated_round})
              </span>
            )}
          </div>
        ))}
      </div>

      <button
        onClick={handlePlayAgain}
        className="font-literary text-[1.1rem] text-ink transition-opacity hover:opacity-70"
      >
        play again &rarr;
      </button>
    </div>
  );
}
